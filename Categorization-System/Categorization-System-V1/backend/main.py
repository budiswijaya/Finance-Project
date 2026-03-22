from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import json
import io
from datetime import UTC, datetime
import re
import hashlib
from functools import lru_cache
from collections import Counter
from collections import deque
from threading import Lock
from time import perf_counter

import psycopg2
from psycopg2.pool import SimpleConnectionPool

import os
from pathlib import Path
from dotenv import load_dotenv


KeywordRule = Tuple[str, int, str]


@lru_cache(maxsize=512)
def _compiled_word_boundary_pattern(keyword: str) -> re.Pattern:
    """Cache compiled regex for repeated word-boundary checks."""
    escaped_keyword = re.escape(keyword)
    return re.compile(rf"\b{escaped_keyword}\b", flags=re.IGNORECASE)


def matches_word_boundary(note_lower: str, keyword_lower: str) -> bool:
    """Return True when keyword appears as a full token (not as part of another word)."""
    return _compiled_word_boundary_pattern(keyword_lower).search(note_lower) is not None


def _normalize_keyword_rule(rule: Tuple[Any, ...]) -> Optional[KeywordRule]:
    """Normalize legacy/partial keyword tuples into a strict (keyword, priority, match_type) shape."""
    if not isinstance(rule, tuple) or len(rule) < 2:
        return None

    keyword = rule[0]
    priority = rule[1]
    match_type = rule[2] if len(rule) >= 3 else "substring"

    if not isinstance(keyword, str) or not keyword.strip():
        return None
    if not isinstance(priority, int):
        priority = 1
    if match_type not in {"substring", "word_boundary", "exact"}:
        match_type = "substring"

    return (keyword.lower().strip(), priority, match_type)


def _note_matches_keyword(note_lower: str, keyword: str, match_type: str) -> bool:
    """Apply one matching strategy for a single keyword rule."""
    if match_type == "exact":
        return note_lower == keyword
    if match_type == "word_boundary":
        return matches_word_boundary(note_lower, keyword)
    return keyword in note_lower


def determine_category_id(
    amount: float,  # Reserved for future amount-based rules; not used in current keyword/name matching
    note: str,
    keywords_by_type: Dict[str, Dict[int, List[Tuple[Any, ...]]]],
    category_names_by_type: Dict[str, Dict[str, int]],
    available_category_names_by_type: Dict[str, List[str]],
    return_metadata: bool = False,
) -> Any:
    """
    Classify a transaction with deterministic keyword/name matching.

    Tie-break rule: lower priority number wins, then lower category ID.
    """
    # Keep one normalized note value so every matching phase is consistent.
    note_lower = note.lower().strip()

    # Merge all category scopes so matching is global and deterministic.
    all_keywords: Dict[int, List[Tuple[Any, ...]]] = {}
    for scoped_keywords in keywords_by_type.values():
        for category_id, keyword_rules in scoped_keywords.items():
            all_keywords.setdefault(category_id, []).extend(keyword_rules)

    all_category_names: Dict[str, int] = {}
    for scoped_names in category_names_by_type.values():
        all_category_names.update(scoped_names)

    all_available_categories: List[str] = []
    for scoped_available in available_category_names_by_type.values():
        all_available_categories.extend(scoped_available)

    # Phase 1: keyword match. We keep only the best keyword per category.
    matched_keywords_by_category: Dict[int, KeywordRule] = {}
    for category_id, raw_rules in all_keywords.items():
        for raw_rule in raw_rules:
            normalized_rule = _normalize_keyword_rule(raw_rule)
            if not normalized_rule:
                continue

            keyword, priority, match_type = normalized_rule
            if _note_matches_keyword(note_lower, keyword, match_type):
                current_best = matched_keywords_by_category.get(category_id)
                if current_best is None or priority < current_best[1]:
                    matched_keywords_by_category[category_id] = (keyword, priority, match_type)

    if matched_keywords_by_category:
        # Final deterministic tie-break across categories.
        best_match = min(matched_keywords_by_category.items(), key=lambda item: (item[1][1], item[0]))
        category_id = best_match[0]
        if return_metadata:
            keyword, priority, match_type = best_match[1]
            return category_id, {
                "phase": 1,
                "resolution_path": "keyword_match",
                "matched_keyword": keyword,
                "match_type": match_type,
                "priority": priority,
            }
        return category_id

    # Phase 2: fallback to category-name matching in note text.
    for category_name, category_id in all_category_names.items():
        if category_name in note_lower:
            if return_metadata:
                return category_id, {
                    "phase": 2,
                    "resolution_path": "category_name_match",
                    "matched_keyword": None,
                    "match_type": None,
                    "priority": None,
                }
            return category_id

    # Phase 3: no match. Build a guidance message for users.
    all_available_keywords: List[str] = []
    for raw_rules in all_keywords.values():
        for raw_rule in raw_rules:
            normalized_rule = _normalize_keyword_rule(raw_rule)
            if normalized_rule:
                keyword, _, _ = normalized_rule
                all_available_keywords.append(keyword)

    keywords_str = ", ".join(sorted(set(all_available_keywords))) if all_available_keywords else "(none defined)"
    categories_str = ", ".join(sorted(set(all_available_categories))) if all_available_categories else "(none defined)"
    error_detail = (
        f"Cannot automatically determine category for '{note}'. "
        f"Available keywords: {keywords_str}. "
        f"You can also include a category name like {categories_str} in the note."
    )

    if return_metadata:
        return None, {
            "phase": 3,
            "resolution_path": "error_no_match",
            "matched_keyword": None,
            "match_type": None,
            "priority": None,
            "error_message": error_detail,
            "available_keywords": sorted(set(all_available_keywords)),
            "available_categories": sorted(set(all_available_categories)),
        }

    raise HTTPException(status_code=400, detail=error_detail)


def hash_note(note: str) -> str:
    """Hash note content so observability logs avoid storing plain text notes."""
    return hashlib.sha256((note or "").encode("utf-8")).hexdigest()


def build_log_payload(
    note: str,
    amount: float,
    transaction_type: str,
    metadata: Dict[str, Any],
    category_id: int,
    category_name: str,
) -> Dict[str, Any]:
    """Normalize classifier output into one database-ready observability payload."""
    phase = metadata.get("phase", 3)
    return {
        "note_hash": hash_note(note),
        "amount": amount,
        "transaction_type": transaction_type,
        "phase_matched": phase,
        "resolution_path": metadata.get("resolution_path") or "error_no_match",
        "matched_keyword": metadata.get("matched_keyword"),
        "matched_category_id": category_id,
        "matched_category_name": category_name,
        "match_type": metadata.get("match_type"),
        "priority": metadata.get("priority"),
        "tie_break_info": metadata.get("tie_break_info"),
        "error_message": metadata.get("error_message"),
    }

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")

DB_POOL_MIN_CONN = 1
DB_POOL_MAX_CONN = int(os.getenv("DB_POOL_MAX_CONN", "5"))

db_pool = SimpleConnectionPool(
    minconn=DB_POOL_MIN_CONN,
    maxconn=DB_POOL_MAX_CONN,
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)

app = FastAPI(title="Data Parser API", version="1.0.0")

ROLLING_WINDOW_SECONDS = 60 * 60
MIN_SAMPLE_SIZE = 100
FAILURE_RATE_ALERT_THRESHOLD = 10.0
PHASE3_RATE_ALERT_THRESHOLD = 20.0
LATENCY_WARNING_THRESHOLD_SECONDS = 1.0

runtime_flags = {
    "merchant_normalization_enabled": False,
}

category_context_cache = {
    "version": None,
    "value": None,
    "rebuilt_at": None,
}
category_context_cache_lock = Lock()

import_observability = {
    "requests": deque(),
    "alerts": deque(maxlen=200),
    "failure_alert_active": False,
    "phase3_alert_active": False,
}
import_observability_lock = Lock()


@contextmanager
def get_db_connection():
    """Acquire one pooled database connection for the duration of a request/task."""
    # Grab a connection from the pool. If all are in use, waits until one is available.
    db_conn = db_pool.getconn()
    try:
        yield db_conn
    finally:
        # Always rollback any uncommitted transaction on exit to avoid leaving open txns.
        # Only explicit db_conn.commit() in try block persists changes.
        try:
            db_conn.rollback()
        except Exception:
            pass
        # Return the connection to the pool. It stays live for reuse by others.
        db_pool.putconn(db_conn)


def get_pool_status() -> Dict[str, int]:
    """Return basic pool sizing information for admin visibility."""
    return {
        "min_connections": DB_POOL_MIN_CONN,
        "max_connections": DB_POOL_MAX_CONN,
    }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _prune_old_requests(now: datetime) -> None:
    """Drop import metric samples outside the rolling one-hour window."""
    window_start = now.timestamp() - ROLLING_WINDOW_SECONDS
    while import_observability["requests"] and import_observability["requests"][0]["timestamp"] < window_start:
        import_observability["requests"].popleft()


def _append_alert(now: datetime, severity: str, message: str, details: Dict[str, Any]) -> None:
    import_observability["alerts"].appendleft(
        {
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "severity": severity,
            "message": message,
            "details": details,
        }
    )


def _evaluate_import_alerts(now: datetime) -> Dict[str, Any]:
    """Evaluate rolling one-hour thresholds for import endpoint metrics."""
    # Prune samples older than 1 hour to maintain a sliding window. deque.popleft() is O(1).
    _prune_old_requests(now)
    requests = list(import_observability["requests"])
    sample_size = len(requests)
    # Aggregate metrics across all requests in the window.

    failure_count = sum(1 for req in requests if req["classification_failed"])
    total_attempted = sum(req["attempted_rows"] for req in requests)
    total_phase3 = sum(req["phase3_rows"] for req in requests)
    # Compute rates as percentages. Handle empty window gracefully.

    failure_rate = (failure_count / sample_size * 100.0) if sample_size else 0.0
    phase3_rate = (total_phase3 / total_attempted * 100.0) if total_attempted else 0.0
    # Only trigger alerts once we have enough samples (dampens noise from early runs).

    if sample_size >= MIN_SAMPLE_SIZE:
            # Alert state machine: trigger on transition from below to above threshold, suppress duplicates.
        failure_now_active = failure_rate > FAILURE_RATE_ALERT_THRESHOLD
        if failure_now_active and not import_observability["failure_alert_active"]:
            _append_alert(
                now,
                "alert",
                "Classification failure rate exceeded threshold",
                {
                    "failure_rate": round(failure_rate, 2),
                    "threshold": FAILURE_RATE_ALERT_THRESHOLD,
                    "sample_size": sample_size,
                    "window": "1h",
                },
            )
        import_observability["failure_alert_active"] = failure_now_active

        phase3_now_active = phase3_rate > PHASE3_RATE_ALERT_THRESHOLD
        if phase3_now_active and not import_observability["phase3_alert_active"]:
            _append_alert(
                now,
                "investigate",
                "Phase 3 fallback rate exceeded threshold",
                {
                    "phase3_rate": round(phase3_rate, 2),
                    "threshold": PHASE3_RATE_ALERT_THRESHOLD,
                    "sample_size": sample_size,
                    "window": "1h",
                },
            )
        import_observability["phase3_alert_active"] = phase3_now_active

    return {
        "window": "1h",
        "sample_size": sample_size,
        "min_sample_size": MIN_SAMPLE_SIZE,
        "classification_failure_rate": round(failure_rate, 2),
        "classification_failure_threshold": FAILURE_RATE_ALERT_THRESHOLD,
        "phase3_fallback_rate": round(phase3_rate, 2),
        "phase3_fallback_threshold": PHASE3_RATE_ALERT_THRESHOLD,
    }


def record_import_metrics(
    latency_seconds: float,
    classification_failed: bool,
    attempted_rows: int,
    phase3_rows: int,
) -> Dict[str, Any]:
    """Record request-level import metrics and return current rolling summary."""
    # Timestamp every metric sample for rolling window calculations and auditing.
    now = _utc_now()
    with import_observability_lock:
        # Append to rolling window deque. Lock ensures no races on list append.
        import_observability["requests"].append(
            {
                "timestamp": now.timestamp(),
                "latency_seconds": latency_seconds,
                "classification_failed": classification_failed,
                "attempted_rows": attempted_rows,
                "phase3_rows": phase3_rows,
            }
        )

        if latency_seconds > LATENCY_WARNING_THRESHOLD_SECONDS:
            _append_alert(
                now,
                "warning",
                "Import API latency exceeded threshold",
                {
                    "endpoint": "POST /transactions/import",
                    "latency_seconds": round(latency_seconds, 4),
                    "threshold": LATENCY_WARNING_THRESHOLD_SECONDS,
                },
            )

        return _evaluate_import_alerts(now)


def get_context_version(cursor) -> int:
    """Read the latest classification context version (0 if table is unavailable)."""
    cursor.execute("SELECT to_regclass('public.classification_context_version')")
    if cursor.fetchone()[0] is None:
        return 0

    cursor.execute("SELECT COALESCE(MAX(version_number), 0) FROM classification_context_version")
    return int(cursor.fetchone()[0] or 0)


def bump_context_version(cursor, reason: str) -> int:
    """Insert a new context version row and return the latest version number."""
    cursor.execute("SELECT to_regclass('public.classification_context_version')")
    if cursor.fetchone()[0] is None:
        return 0

    # Serialize version bumps to prevent duplicate version_number during concurrent writes.
    # Advisory lock is transaction-scoped: held until commit/rollback. Fixed ID 31996085.
    cursor.execute("SELECT pg_advisory_xact_lock(%s)", (31996085,))
    # Read current max and atomically insert next version while lock is held.
    cursor.execute("SELECT COALESCE(MAX(version_number), 0) FROM classification_context_version")
    latest_version = int(cursor.fetchone()[0] or 0)
    next_version = latest_version + 1
    cursor.execute(
        """
        INSERT INTO classification_context_version (version_number, reason, created_at)
        VALUES (%s, %s, NOW())
        """,
        (next_version, reason),
    )
    return next_version


def invalidate_category_context_cache() -> None:
    """Invalidate the in-memory classification context cache immediately."""
    with category_context_cache_lock:
        category_context_cache["version"] = None
        category_context_cache["value"] = None
        category_context_cache["rebuilt_at"] = None


def load_active_merchant_normalization_rules(cursor) -> List[Dict[str, Any]]:
    """Load active merchant normalization rules ordered by priority then id."""
    cursor.execute("SELECT to_regclass('public.merchant_normalization_rules')")
    if cursor.fetchone()[0] is None:
        return []

    cursor.execute(
        """
        SELECT id, pattern, replacement, match_type, priority
        FROM merchant_normalization_rules
        WHERE COALESCE(is_active, TRUE) = TRUE
        ORDER BY priority ASC, id ASC
        """
    )
    rows = cursor.fetchall()
    return [
        {
            "id": row[0],
            "pattern": row[1],
            "replacement": row[2],
            "match_type": row[3],
            "priority": row[4],
        }
        for row in rows
    ]


def _apply_normalization_rule(text: str, pattern: str, replacement: str, match_type: str) -> str:
    if match_type == "exact":
        return replacement if text == pattern else text
    if match_type == "word_boundary":
        return re.sub(rf"\b{re.escape(pattern)}\b", replacement, text)
    return text.replace(pattern, replacement)


def normalize_merchant_note(note: str, rules: List[Dict[str, Any]]) -> str:
    """Normalize notes deterministically using global active rules."""
    normalized = (note or "").lower().strip()
    for rule in rules:
        pattern = rule.get("pattern")
        replacement = rule.get("replacement")
        match_type = rule.get("match_type")
        if not isinstance(pattern, str) or not pattern.strip():
            continue
        if not isinstance(replacement, str):
            replacement = ""
        if match_type not in {"substring", "word_boundary", "exact"}:
            match_type = "substring"
        normalized = _apply_normalization_rule(normalized, pattern.lower().strip(), replacement.lower().strip(), match_type)
    return normalized.strip()

# CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/categories")
async def get_categories():
    """Get all categories from database"""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute("SELECT id, name, icon, type FROM categories ORDER BY name")
            rows = cursor.fetchall()

        categories = []
        for row in rows:
            categories.append({
                "id": row[0],
                "name": row[1],
                "icon": row[2],
                "type": row[3]
            })

        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")


@app.put("/categories/{category_id}")
async def update_category(category_id: int, payload: Dict[str, Any]):
    """Update an existing category's user-facing fields."""
    try:
        updates = []
        values = []

        if "name" in payload:
            name = payload.get("name")
            if not isinstance(name, str) or not name.strip():
                raise HTTPException(status_code=422, detail="name must be a non-empty string")
            updates.append("name = %s")
            values.append(name.strip())

        if "icon" in payload:
            icon = payload.get("icon")
            if icon is not None and not isinstance(icon, str):
                raise HTTPException(status_code=422, detail="icon must be a string or null")
            updates.append("icon = %s")
            values.append(icon)

        if "type" in payload:
            category_type = payload.get("type")
            if not isinstance(category_type, str) or category_type.strip() not in {"income", "expense"}:
                raise HTTPException(status_code=422, detail="type must be either 'income' or 'expense'")
            updates.append("type = %s")
            values.append(category_type.strip())

        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields provided for update")

        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()

            cursor.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Category not found")

            values.append(category_id)
            cursor.execute(
                f"""
                UPDATE categories
                SET {', '.join(updates)}
                WHERE id = %s
                RETURNING id, name, icon, type
                """,
                tuple(values),
            )
            row = cursor.fetchone()
            bump_context_version(cursor, "category_update")
            db_conn.commit()

        invalidate_category_context_cache()

        return {
            "id": row[0],
            "name": row[1],
            "icon": row[2],
            "type": row[3],
        }
    except HTTPException:
        raise
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Category name already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update category: {str(e)}")


@app.post("/categories")
async def create_category(payload: Dict[str, Any]):
    """Create a new category for user-managed classification."""
    try:
        name = payload.get("name")
        icon = payload.get("icon")
        category_type = payload.get("type")

        if not isinstance(name, str) or not name.strip():
            raise HTTPException(status_code=422, detail="name must be a non-empty string")
        if icon is not None and not isinstance(icon, str):
            raise HTTPException(status_code=422, detail="icon must be a string or null")
        if not isinstance(category_type, str) or category_type.strip() not in {"income", "expense"}:
            raise HTTPException(status_code=422, detail="type must be either 'income' or 'expense'")

        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO categories (name, icon, type)
                VALUES (%s, %s, %s)
                RETURNING id, name, icon, type
                """,
                (name.strip(), icon, category_type.strip()),
            )
            row = cursor.fetchone()
            bump_context_version(cursor, "category_create")
            db_conn.commit()

        invalidate_category_context_cache()
        return {
            "id": row[0],
            "name": row[1],
            "icon": row[2],
            "type": row[3],
        }
    except HTTPException:
        raise
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Category name already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create category: {str(e)}")


@app.post("/admin/categories")
async def create_category_admin(payload: Dict[str, Any]):
    """Admin alias for category creation to keep frontend/backends path-compatible."""
    return await create_category(payload)


@app.get("/categories/{category_id}/usage")
async def get_category_usage(category_id: int):
    """Return usage counters so UI can require explicit confirmation before delete."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute("SELECT id, name FROM categories WHERE id = %s", (category_id,))
            category_row = cursor.fetchone()
            if category_row is None:
                raise HTTPException(status_code=404, detail="Category not found")

            cursor.execute("SELECT COUNT(*) FROM transactions WHERE category_id = %s", (category_id,))
            transaction_count = int(cursor.fetchone()[0] or 0)

            cursor.execute("SELECT COUNT(*) FROM category_keywords WHERE category_id = %s", (category_id,))
            keyword_count = int(cursor.fetchone()[0] or 0)

        return {
            "id": category_row[0],
            "name": category_row[1],
            "transaction_count": transaction_count,
            "keyword_count": keyword_count,
            "requires_force": transaction_count > 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch category usage: {str(e)}")


@app.get("/admin/categories/{category_id}/usage")
async def get_category_usage_admin(category_id: int):
    """Admin alias for category usage check."""
    return await get_category_usage(category_id)


@app.delete("/categories/{category_id}")
async def delete_category(category_id: int, force: bool = Query(default=False)):
    """Delete a category, requiring force when transactions already exist."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute("SELECT id, name FROM categories WHERE id = %s", (category_id,))
            category_row = cursor.fetchone()
            if category_row is None:
                raise HTTPException(status_code=404, detail="Category not found")

            cursor.execute("SELECT COUNT(*) FROM transactions WHERE category_id = %s", (category_id,))
            transaction_count = int(cursor.fetchone()[0] or 0)

            if transaction_count > 0 and not force:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Category has linked transactions and requires force delete confirmation",
                        "category_id": category_id,
                        "transaction_count": transaction_count,
                    },
                )

            deleted_transactions = 0
            if force and transaction_count > 0:
                cursor.execute("DELETE FROM transactions WHERE category_id = %s", (category_id,))
                deleted_transactions = cursor.rowcount

            cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Category not found")

            bump_context_version(cursor, "category_delete")
            db_conn.commit()

        invalidate_category_context_cache()
        return {
            "deleted": True,
            "id": category_id,
            "name": category_row[1],
            "deleted_transactions": deleted_transactions,
            "force": force,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete category: {str(e)}")


@app.put("/admin/categories/{category_id}")
async def update_category_admin(category_id: int, payload: Dict[str, Any]):
    """Admin alias for category update."""
    return await update_category(category_id, payload)


@app.delete("/admin/categories/{category_id}")
async def delete_category_admin(category_id: int, force: bool = Query(default=False)):
    """Admin alias for category delete."""
    return await delete_category(category_id, force)

@app.get("/categories/types")
async def get_category_types():
    """Get distinct category types (income, expense)"""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute("SELECT DISTINCT type FROM categories WHERE type IS NOT NULL")
            rows = cursor.fetchall()

        types = [row[0] for row in rows]
        return {"types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch category types: {str(e)}")


def normalize_keyword(value: str) -> str:
    """Normalize keyword input for matching and duplicate checks."""
    return value.lower().strip()


def validate_match_type(value: str) -> str:
    """Validate one of the supported keyword match strategies."""
    allowed = {"substring", "word_boundary", "exact"}
    if value not in allowed:
        raise HTTPException(status_code=422, detail="match_type must be one of: substring, word_boundary, exact")
    return value


def get_table_columns(cursor, table_name: str) -> set:
    """Return existing column names for a table in public schema."""
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return {row[0] for row in cursor.fetchall()}


def load_category_context(cursor):
    """Load categories and active keyword rules into per-type in-memory maps."""
    # Detect schema evolution: check for match_type and is_active columns to support migrations.
    keyword_columns = get_table_columns(cursor, "category_keywords")
    has_match_type = "match_type" in keyword_columns
    has_is_active = "is_active" in keyword_columns

    # Build SQL dynamically to handle both old/new schema. Defaults: substring matching, active=true.
    match_type_select = "COALESCE(ck.match_type, 'substring')" if has_match_type else "'substring'"
    active_filter = "AND COALESCE(ck.is_active, TRUE) = TRUE" if has_is_active else ""

    # Single query aggregates all keywords per category as JSON. Group ensures one row per category.
    cursor.execute(
        f"""
        SELECT c.id, c.name, c.type,
               COALESCE(
                   json_agg(
                       json_build_object(
                           'keyword', ck.keyword,
                           'priority', ck.priority,
                           'match_type', {match_type_select}
                       )
                       ORDER BY ck.priority ASC, ck.id ASC
                   ) FILTER (WHERE ck.id IS NOT NULL),
                   '[]'
               ) as keywords
        FROM categories c
        LEFT JOIN category_keywords ck
               ON c.id = ck.category_id
              {active_filter}
        GROUP BY c.id, c.name, c.type
        ORDER BY c.name
        """
    )

    # Build four parallel maps for fast lookup during classification.
    categories = cursor.fetchall()
    keywords_by_type = {"income": {}, "expense": {}}  # [ type ] -> { category_id -> [(keyword, priority, match_type), ...] }
    category_names_by_type = {"income": {}, "expense": {}}  # [ type ] -> { normalized_name -> category_id }
    available_category_names_by_type = {"income": [], "expense": []}  # [ type ] -> [ original_name, ... ]
    category_lookup = {}  # { category_id -> { name, type } } for reverse name lookup

    for cat_id, cat_name, cat_type, keywords_json in categories:
        if cat_type not in keywords_by_type:
            continue

        # Register category name for Phase 2 fallback (substring match on category name in note).
        normalized_name = cat_name.lower().strip()
        category_names_by_type[cat_type][normalized_name] = cat_id
        available_category_names_by_type[cat_type].append(cat_name)
        category_lookup[cat_id] = {"name": cat_name, "type": cat_type}

        # Clean and deduplicate keywords. Validate each keyword tuple for schema compliance.
        cleaned_keywords = []
        for kw in keywords_json or []:
            keyword = kw.get("keyword") if isinstance(kw, dict) else None
            priority = kw.get("priority") if isinstance(kw, dict) else None
            match_type = kw.get("match_type") if isinstance(kw, dict) else "substring"
            if isinstance(keyword, str) and keyword.strip():
                cleaned_keywords.append(
                    (
                        normalize_keyword(keyword),
                        priority if isinstance(priority, int) else 1,
                        validate_match_type(match_type if isinstance(match_type, str) else "substring"),
                    )
                )

        # Store cleaned keywords only if list is non-empty to keep map sparse.
        if cleaned_keywords:
            keywords_by_type[cat_type][cat_id] = cleaned_keywords

    return keywords_by_type, category_names_by_type, available_category_names_by_type, category_lookup


def get_classification_context(cursor, force_rebuild: bool = False):
    """Return classification context from cache or rebuild from DB snapshot."""
    # Read current DB version number. Tracked in classification_context_version table.
    db_version = get_context_version(cursor)

    with category_context_cache_lock:
        # Cache hit: if version hasn't changed, reuse in-memory context (fast path).
        if (
            not force_rebuild
            and category_context_cache["value"] is not None
            and category_context_cache["version"] == db_version
        ):
            return category_context_cache["value"], {
                "source": "cache",
                "version": db_version,
                "rebuilt_at": category_context_cache["rebuilt_at"],
            }

    # Cache miss or stale: rebuild from DB. Expensive but ensures consistency after mutations.
    context_value = load_category_context(cursor)
    rebuilt_at = _utc_now().isoformat() + "Z"
    rebuilt_at = rebuilt_at.replace("+00:00Z", "Z")

    # Store new context with its version. Next request with same version will hit cache.
    with category_context_cache_lock:
        category_context_cache["value"] = context_value
        category_context_cache["version"] = db_version
        category_context_cache["rebuilt_at"] = rebuilt_at

    return context_value, {
        "source": "db_rebuild",
        "version": db_version,
        "rebuilt_at": rebuilt_at,
    }


def is_classification_log_available(cursor) -> bool:
    """Detect whether Phase 2 observability table exists."""
    cursor.execute("SELECT to_regclass('public.transaction_classification_log')")
    return cursor.fetchone()[0] is not None


def log_classification(cursor, transaction_id: int, payload: Dict[str, Any]) -> None:
    """Insert one observability row for classifier outcomes."""
    cursor.execute(
        """
        INSERT INTO transaction_classification_log (
            transaction_id,
            note_hash,
            amount,
            transaction_type,
            phase_matched,
            resolution_path,
            matched_keyword,
            matched_category_id,
            matched_category_name,
            match_type,
            priority,
            tie_break_info,
            error_message,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            transaction_id,
            payload.get("note_hash"),
            payload.get("amount"),
            payload.get("transaction_type"),
            payload.get("phase_matched"),
            payload.get("resolution_path"),
            payload.get("matched_keyword"),
            payload.get("matched_category_id"),
            payload.get("matched_category_name"),
            payload.get("match_type"),
            payload.get("priority"),
            payload.get("tie_break_info"),
            payload.get("error_message"),
        ),
    )

@app.get("/category-keywords")
async def get_category_keywords(
    category_id: Optional[int] = Query(default=None),
    type: Optional[str] = Query(default=None),
    active: Optional[bool] = Query(default=True),
    match_type: Optional[str] = Query(default=None),
):
    """List keyword rules with optional filters."""
    try:
        if type is not None and type not in {"income", "expense"}:
            raise HTTPException(status_code=422, detail="type must be either income or expense")
        if match_type is not None:
            validate_match_type(match_type)

        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            where_clauses = []
            params = []

            if category_id is not None:
                where_clauses.append("ck.category_id = %s")
                params.append(category_id)
            if type is not None:
                where_clauses.append("c.type = %s")
                params.append(type)
            if active is not None:
                where_clauses.append("COALESCE(ck.is_active, TRUE) = %s")
                params.append(active)
            if match_type is not None:
                where_clauses.append("COALESCE(ck.match_type, 'substring') = %s")
                params.append(match_type)

            query = """
                SELECT ck.id, ck.category_id, c.name, c.type, ck.keyword, ck.priority,
                       COALESCE(ck.match_type, 'substring') AS match_type,
                       COALESCE(ck.is_active, TRUE) AS is_active,
                       ck.created_by, ck.created_at, ck.updated_at
                FROM category_keywords ck
                JOIN categories c ON c.id = ck.category_id
            """
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            query += " ORDER BY c.name, ck.priority ASC, ck.id ASC"

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

        keywords = [
            {
                "id": row[0],
                "category_id": row[1],
                "category_name": row[2],
                "type": row[3],
                "keyword": row[4],
                "priority": row[5],
                "match_type": row[6],
                "is_active": row[7],
                "created_by": row[8],
                "created_at": row[9],
                "updated_at": row[10],
            }
            for row in rows
        ]
        return {"keywords": keywords, "total": len(keywords)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch category keywords: {str(e)}")


@app.post("/category-keywords")
async def create_category_keyword(payload: Dict[str, Any]):
    """Create one keyword rule for a category."""
    try:
        category_id = payload.get("category_id")
        keyword = payload.get("keyword")
        priority = payload.get("priority", 1)
        match_type = payload.get("match_type", "substring")
        created_by = payload.get("created_by")

        if not isinstance(category_id, int):
            raise HTTPException(status_code=422, detail="category_id is required and must be an integer")
        if not isinstance(keyword, str) or not keyword.strip():
            raise HTTPException(status_code=422, detail="keyword is required")
        if not isinstance(priority, int) or priority < 1:
            raise HTTPException(status_code=422, detail="priority must be a positive integer")
        if not isinstance(match_type, str):
            raise HTTPException(status_code=422, detail="match_type must be a string")
        validate_match_type(match_type)

        normalized_keyword = normalize_keyword(keyword)
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()

            cursor.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=400, detail="Category does not exist")

            cursor.execute(
                """
                SELECT id
                FROM category_keywords
                WHERE category_id = %s
                  AND LOWER(TRIM(keyword)) = %s
                  AND COALESCE(is_active, TRUE) = TRUE
                """,
                (category_id, normalized_keyword),
            )
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=409, detail=f"Keyword '{normalized_keyword}' already exists for this category")

            cursor.execute(
                """
                INSERT INTO category_keywords (category_id, keyword, priority, match_type, is_active, created_by, updated_at)
                VALUES (%s, %s, %s, %s, TRUE, %s, NOW())
                RETURNING id, category_id, keyword, priority, match_type, is_active, created_by, created_at, updated_at
                """,
                (category_id, normalized_keyword, priority, match_type, created_by),
            )
            row = cursor.fetchone()
            bump_context_version(cursor, "category_keyword_create")
            db_conn.commit()
        invalidate_category_context_cache()

        return {
            "id": row[0],
            "category_id": row[1],
            "keyword": row[2],
            "priority": row[3],
            "match_type": row[4],
            "is_active": row[5],
            "created_by": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create category keyword: {str(e)}")


@app.put("/category-keywords/{keyword_id}")
async def update_category_keyword(keyword_id: int, payload: Dict[str, Any]):
    """Update an existing keyword rule."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                SELECT id, category_id, keyword, priority, COALESCE(match_type, 'substring'), COALESCE(is_active, TRUE)
                FROM category_keywords
                WHERE id = %s
                """,
                (keyword_id,),
            )
            existing = cursor.fetchone()
            if existing is None:
                raise HTTPException(status_code=404, detail="Keyword rule not found")

            category_id = existing[1]
            updates = []
            values = []

            if "keyword" in payload:
                if not isinstance(payload["keyword"], str) or not payload["keyword"].strip():
                    raise HTTPException(status_code=422, detail="keyword must be a non-empty string")
                normalized_keyword = normalize_keyword(payload["keyword"])
                cursor.execute(
                    """
                    SELECT id
                    FROM category_keywords
                    WHERE category_id = %s
                      AND LOWER(TRIM(keyword)) = %s
                      AND id <> %s
                      AND COALESCE(is_active, TRUE) = TRUE
                    """,
                    (category_id, normalized_keyword, keyword_id),
                )
                if cursor.fetchone() is not None:
                    raise HTTPException(status_code=409, detail=f"Keyword '{normalized_keyword}' already exists for this category")
                updates.append("keyword = %s")
                values.append(normalized_keyword)

            if "priority" in payload:
                if not isinstance(payload["priority"], int) or payload["priority"] < 1:
                    raise HTTPException(status_code=422, detail="priority must be a positive integer")
                updates.append("priority = %s")
                values.append(payload["priority"])

            if "match_type" in payload:
                if not isinstance(payload["match_type"], str):
                    raise HTTPException(status_code=422, detail="match_type must be a string")
                updates.append("match_type = %s")
                values.append(validate_match_type(payload["match_type"]))

            if "is_active" in payload:
                if not isinstance(payload["is_active"], bool):
                    raise HTTPException(status_code=422, detail="is_active must be a boolean")
                updates.append("is_active = %s")
                values.append(payload["is_active"])

            if not updates:
                raise HTTPException(status_code=400, detail="No valid fields provided for update")

            updates.append("updated_at = NOW()")
            values.append(keyword_id)

            cursor.execute(
                f"""
                UPDATE category_keywords
                SET {', '.join(updates)}
                WHERE id = %s
                RETURNING id, category_id, keyword, priority, COALESCE(match_type, 'substring'),
                          COALESCE(is_active, TRUE), created_by, created_at, updated_at
                """,
                tuple(values),
            )
            row = cursor.fetchone()
            bump_context_version(cursor, "category_keyword_update")
            db_conn.commit()
        invalidate_category_context_cache()

        return {
            "id": row[0],
            "category_id": row[1],
            "keyword": row[2],
            "priority": row[3],
            "match_type": row[4],
            "is_active": row[5],
            "created_by": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update category keyword: {str(e)}")


@app.delete("/category-keywords/{keyword_id}", status_code=204)
async def delete_category_keyword(keyword_id: int):
    """Soft-delete one keyword rule by marking it inactive."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                UPDATE category_keywords
                SET is_active = FALSE,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id
                """,
                (keyword_id,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Keyword rule not found")

            bump_context_version(cursor, "category_keyword_soft_delete")
            db_conn.commit()
        invalidate_category_context_cache()
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete category keyword: {str(e)}")


@app.post("/category-keywords/validate-note")
async def validate_category_note(payload: Dict[str, Any]):
    """Classify a note without inserting a transaction."""
    try:
        note = payload.get("note", "")
        amount = payload.get("amount")

        if amount is None or not isinstance(amount, (int, float)):
            raise HTTPException(status_code=422, detail="amount is required and must be a number")
        if not isinstance(note, str):
            raise HTTPException(status_code=422, detail="note must be a string")

        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            (keywords_by_type, category_names_by_type, available_category_names_by_type, category_lookup), cache_meta = get_classification_context(cursor)
            normalization_rules = load_active_merchant_normalization_rules(cursor)

            normalized_note = note
            if runtime_flags["merchant_normalization_enabled"]:
                normalized_note = normalize_merchant_note(note, normalization_rules)

            category_id, metadata = determine_category_id(
                amount=amount,
                note=normalized_note,
                keywords_by_type=keywords_by_type,
                category_names_by_type=category_names_by_type,
                available_category_names_by_type=available_category_names_by_type,
                return_metadata=True,
            )

        if category_id is None:
            return {
                "classification_scope": "global",
                "cache_meta": cache_meta,
                "merchant_normalization_enabled": runtime_flags["merchant_normalization_enabled"],
                "normalized_note": normalized_note,
                "classification": metadata,
            }

        return {
            "classification_scope": "global",
            "cache_meta": cache_meta,
            "merchant_normalization_enabled": runtime_flags["merchant_normalization_enabled"],
            "normalized_note": normalized_note,
            "classification": {
                "category_id": category_id,
                "category_name": category_lookup.get(category_id, {}).get("name"),
                "phase": metadata.get("phase"),
                "resolution_path": metadata.get("resolution_path"),
                "matched_keyword": metadata.get("matched_keyword"),
                "match_type": metadata.get("match_type"),
                "priority": metadata.get("priority"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate note: {str(e)}")


@app.get("/category-keywords/coverage")
async def get_category_keyword_coverage(type: Optional[str] = Query(default=None)):
    """Return active keyword coverage summary by category."""
    try:
        if type is not None and type not in {"income", "expense"}:
            raise HTTPException(status_code=422, detail="type must be either income or expense")

        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            where_clause = ""
            params = []
            if type is not None:
                where_clause = "WHERE c.type = %s"
                params.append(type)

            cursor.execute(
                f"""
                SELECT c.id, c.name, c.type,
                       COUNT(ck.id) FILTER (WHERE COALESCE(ck.is_active, TRUE) = TRUE) AS active_keyword_count,
                       COALESCE(
                           json_agg(
                               json_build_object(
                                   'keyword', ck.keyword,
                                   'priority', ck.priority,
                                   'match_type', COALESCE(ck.match_type, 'substring')
                               )
                               ORDER BY ck.priority ASC, ck.id ASC
                           ) FILTER (WHERE ck.id IS NOT NULL AND COALESCE(ck.is_active, TRUE) = TRUE),
                           '[]'
                       ) AS keywords
                FROM categories c
                LEFT JOIN category_keywords ck ON c.id = ck.category_id
                {where_clause}
                GROUP BY c.id, c.name, c.type
                ORDER BY c.name
                """,
                tuple(params),
            )
            rows = cursor.fetchall()

        categories = []
        categories_without_rules = []
        for row in rows:
            keywords = row[4] or []
            priority_distribution = Counter(str(k.get("priority", 1)) for k in keywords)
            match_type_distribution = Counter(k.get("match_type", "substring") for k in keywords)

            category_payload = {
                "id": row[0],
                "name": row[1],
                "type": row[2],
                "active_keyword_count": row[3],
                "keywords": [k.get("keyword") for k in keywords if isinstance(k.get("keyword"), str)],
                "priority_distribution": dict(priority_distribution),
                "match_type_distribution": {
                    "substring": match_type_distribution.get("substring", 0),
                    "word_boundary": match_type_distribution.get("word_boundary", 0),
                    "exact": match_type_distribution.get("exact", 0),
                },
            }
            categories.append(category_payload)
            if row[3] == 0:
                categories_without_rules.append({"id": row[0], "name": row[1], "type": row[2]})

        categories_with_rules = len([c for c in categories if c["active_keyword_count"] > 0])
        total_rules = sum(c["active_keyword_count"] for c in categories)

        return {
            "categories": categories,
            "summary": {
                "total_categories": len(categories),
                "categories_with_rules": categories_with_rules,
                "categories_without_rules": len(categories) - categories_with_rules,
                "total_active_rules": total_rules,
            },
            "categories_without_rules": categories_without_rules,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get keyword coverage: {str(e)}")


@app.get("/admin/feature-flags")
async def get_feature_flags():
    """Return runtime feature flags for backend-only Phase 3 toggles."""
    return {"feature_flags": runtime_flags.copy()}


@app.put("/admin/feature-flags/merchant-normalization")
async def update_merchant_normalization_feature_flag(payload: Dict[str, Any]):
    """Enable/disable merchant note normalization in classification path."""
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=422, detail="enabled must be a boolean")

    runtime_flags["merchant_normalization_enabled"] = enabled
    return {
        "merchant_normalization_enabled": runtime_flags["merchant_normalization_enabled"],
    }


@app.get("/admin/classification-context")
async def get_classification_context_status():
    """Inspect in-memory cache status and latest DB version for classification context."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            db_version = get_context_version(cursor)
        with category_context_cache_lock:
            cache_version = category_context_cache["version"]
            rebuilt_at = category_context_cache["rebuilt_at"]
            is_warm = category_context_cache["value"] is not None
        return {
            "db_version": db_version,
            "cache_version": cache_version,
            "cache_warm": is_warm,
            "rebuilt_at": rebuilt_at,
            "pool": get_pool_status(),
            "merchant_normalization_enabled": runtime_flags["merchant_normalization_enabled"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch classification context status: {str(e)}")


@app.post("/admin/classification-context/refresh")
async def force_refresh_classification_context():
    """Force a full cache rebuild regardless of current version."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            context_value, cache_meta = get_classification_context(cursor, force_rebuild=True)
        keywords_by_type, _, _, _ = context_value
        total_active_rules = sum(len(v) for by_type in keywords_by_type.values() for v in by_type.values())
        return {
            "refreshed": True,
            "forced": True,
            "cache_meta": cache_meta,
            "total_active_rules": total_active_rules,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh classification context: {str(e)}")


@app.get("/admin/merchant-normalization-rules")
async def get_merchant_normalization_rules(active: Optional[bool] = Query(default=True)):
    """List merchant normalization rules."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute("SELECT to_regclass('public.merchant_normalization_rules')")
            if cursor.fetchone()[0] is None:
                return {"rules": [], "total": 0}

            query = """
                SELECT id, pattern, replacement, match_type, priority,
                       COALESCE(is_active, TRUE) AS is_active,
                       created_at, updated_at
                FROM merchant_normalization_rules
            """
            params = []
            if active is not None:
                query += " WHERE COALESCE(is_active, TRUE) = %s"
                params.append(active)
            query += " ORDER BY priority ASC, id ASC"

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        rules = [
            {
                "id": row[0],
                "pattern": row[1],
                "replacement": row[2],
                "match_type": row[3],
                "priority": row[4],
                "is_active": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
            for row in rows
        ]
        return {"rules": rules, "total": len(rules)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch merchant normalization rules: {str(e)}")


@app.post("/admin/merchant-normalization-rules")
async def create_merchant_normalization_rule(payload: Dict[str, Any]):
    """Create one global merchant normalization rule."""
    try:
        pattern = payload.get("pattern")
        replacement = payload.get("replacement", "")
        priority = payload.get("priority", 1)
        match_type = payload.get("match_type", "substring")

        if not isinstance(pattern, str) or not pattern.strip():
            raise HTTPException(status_code=422, detail="pattern is required")
        if not isinstance(replacement, str):
            raise HTTPException(status_code=422, detail="replacement must be a string")
        if not isinstance(priority, int) or priority < 1:
            raise HTTPException(status_code=422, detail="priority must be a positive integer")
        if not isinstance(match_type, str):
            raise HTTPException(status_code=422, detail="match_type must be a string")
        validate_match_type(match_type)

        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO merchant_normalization_rules (pattern, replacement, match_type, priority, is_active, updated_at)
                VALUES (%s, %s, %s, %s, TRUE, NOW())
                RETURNING id, pattern, replacement, match_type, priority, COALESCE(is_active, TRUE), created_at, updated_at
                """,
                (pattern.lower().strip(), replacement.lower().strip(), match_type, priority),
            )
            row = cursor.fetchone()
            bump_context_version(cursor, "merchant_normalization_rule_create")
            db_conn.commit()
        invalidate_category_context_cache()
        return {
            "id": row[0],
            "pattern": row[1],
            "replacement": row[2],
            "match_type": row[3],
            "priority": row[4],
            "is_active": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create merchant normalization rule: {str(e)}")


@app.put("/admin/merchant-normalization-rules/{rule_id}")
async def update_merchant_normalization_rule(rule_id: int, payload: Dict[str, Any]):
    """Update an existing global merchant normalization rule."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            updates = []
            values = []

            if "pattern" in payload:
                if not isinstance(payload["pattern"], str) or not payload["pattern"].strip():
                    raise HTTPException(status_code=422, detail="pattern must be a non-empty string")
                updates.append("pattern = %s")
                values.append(payload["pattern"].lower().strip())

            if "replacement" in payload:
                if not isinstance(payload["replacement"], str):
                    raise HTTPException(status_code=422, detail="replacement must be a string")
                updates.append("replacement = %s")
                values.append(payload["replacement"].lower().strip())

            if "match_type" in payload:
                if not isinstance(payload["match_type"], str):
                    raise HTTPException(status_code=422, detail="match_type must be a string")
                updates.append("match_type = %s")
                values.append(validate_match_type(payload["match_type"]))

            if "priority" in payload:
                if not isinstance(payload["priority"], int) or payload["priority"] < 1:
                    raise HTTPException(status_code=422, detail="priority must be a positive integer")
                updates.append("priority = %s")
                values.append(payload["priority"])

            if "is_active" in payload:
                if not isinstance(payload["is_active"], bool):
                    raise HTTPException(status_code=422, detail="is_active must be a boolean")
                updates.append("is_active = %s")
                values.append(payload["is_active"])

            if not updates:
                raise HTTPException(status_code=400, detail="No valid fields provided for update")

            updates.append("updated_at = NOW()")
            values.append(rule_id)

            cursor.execute(
                f"""
                UPDATE merchant_normalization_rules
                SET {', '.join(updates)}
                WHERE id = %s
                RETURNING id, pattern, replacement, match_type, priority, COALESCE(is_active, TRUE), created_at, updated_at
                """,
                tuple(values),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Merchant normalization rule not found")

            bump_context_version(cursor, "merchant_normalization_rule_update")
            db_conn.commit()
        invalidate_category_context_cache()
        return {
            "id": row[0],
            "pattern": row[1],
            "replacement": row[2],
            "match_type": row[3],
            "priority": row[4],
            "is_active": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update merchant normalization rule: {str(e)}")


@app.delete("/admin/merchant-normalization-rules/{rule_id}", status_code=204)
async def delete_merchant_normalization_rule(rule_id: int):
    """Soft-delete merchant normalization rules for safe rollback."""
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                UPDATE merchant_normalization_rules
                SET is_active = FALSE,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id
                """,
                (rule_id,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Merchant normalization rule not found")

            bump_context_version(cursor, "merchant_normalization_rule_soft_delete")
            db_conn.commit()
        invalidate_category_context_cache()
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete merchant normalization rule: {str(e)}")


@app.post("/admin/merchant-normalization-rules/validate-note")
async def validate_merchant_normalization_note(payload: Dict[str, Any]):
    """Preview how active normalization rules transform a note."""
    note = payload.get("note", "")
    if not isinstance(note, str):
        raise HTTPException(status_code=422, detail="note must be a string")

    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()
            rules = load_active_merchant_normalization_rules(cursor)
        normalized_note = normalize_merchant_note(note, rules)
        return {
            "note": note,
            "normalized_note": normalized_note,
            "rules_applied": len(rules),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate merchant normalization note: {str(e)}")


@app.get("/admin/observability/summary")
async def get_observability_summary():
    """Return rolling one-hour summary for import endpoint alerts and thresholds."""
    with import_observability_lock:
        summary = _evaluate_import_alerts(_utc_now())
        latest_alert = import_observability["alerts"][0] if import_observability["alerts"] else None
    return {
        "endpoint": "POST /transactions/import",
        "latency_warning_threshold_seconds": LATENCY_WARNING_THRESHOLD_SECONDS,
        "summary": summary,
        "latest_alert": latest_alert,
    }


@app.get("/admin/observability/alerts")
async def get_observability_alerts(limit: int = Query(default=20)):
    """Return recent in-memory alert and warning events."""
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    with import_observability_lock:
        alerts = list(import_observability["alerts"])[:limit]
    return {"alerts": alerts, "total": len(alerts)}


@app.post("/transactions/import")
async def import_transactions(rows: List[Dict[str, Any]], debug: bool = Query(default=False)):
    """Import transactions with deterministic category assignment."""
    started_at = perf_counter()
    classification_failed = False
    attempted_rows = 0
    phase3_rows = 0
    try:
        with get_db_connection() as db_conn:
            cursor = db_conn.cursor()

            # Guard: ensure categories table is populated before allowing imports.
            cursor.execute("SELECT COUNT(*) FROM categories")
            category_count = cursor.fetchone()[0]
            if category_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail="You should define categories in database first to submit data.",
                )

            # Load classification context once per request. Cache hit if DB version unchanged.
            (keywords_by_type, category_names_by_type, available_category_names_by_type, category_lookup), cache_meta = get_classification_context(cursor)
            logging_enabled = is_classification_log_available(cursor)
            normalization_rules = load_active_merchant_normalization_rules(cursor)  # Applied if enabled.

            inserted_count = 0
            classifications = []  # Debug output: per-row classification results.

            # Process each transaction: validate, normalize, classify, insert, and log (if enabled).
            for r in rows:
                if not r.get("date"):
                    raise HTTPException(status_code=400, detail=f"Date is required for transaction: {r}")

                amount = r.get("amount")
                if amount is None or not isinstance(amount, (int, float)):
                    raise HTTPException(status_code=400, detail=f"Valid amount is required for transaction: {r}")

                # Normalize note if merchant normalization is enabled. Applied before classification.
                note = r.get("note") or r.get("description") or ""
                normalized_note = note
                if runtime_flags["merchant_normalization_enabled"]:
                    normalized_note = normalize_merchant_note(note, normalization_rules)

                attempted_rows += 1
                # Deterministic classification with metadata tracking (phase 1, 2, or 3).
                category_id, metadata = determine_category_id(
                    amount=amount,
                    note=normalized_note,
                    keywords_by_type=keywords_by_type,
                    category_names_by_type=category_names_by_type,
                    available_category_names_by_type=available_category_names_by_type,
                    return_metadata=True,
                )

                if category_id is None:
                    # No matching category at all (phase 3 failure). Stop import.
                    classification_failed = True
                    phase3_rows += 1
                    raise HTTPException(status_code=400, detail=metadata.get("error_message"))

                # Insert transaction with assigned category. Store original note, not normalized.
                cursor.execute(
                    """
                    INSERT INTO transactions (date, amount, note, category_id, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    RETURNING id
                    """,
                    (r["date"], amount, note, category_id),
                )
                transaction_id = cursor.fetchone()[0]
                inserted_count += 1

                # Deduce transaction type from amount sign for observability logging.
                category_name = category_lookup.get(category_id, {}).get("name")
                transaction_type = "income" if amount > 0 else "expense"

                # Log classification outcome to transaction_classification_log for audit trail.
                if logging_enabled:
                    payload = build_log_payload(
                        note=note,
                        amount=amount,
                        transaction_type=transaction_type,
                        metadata=metadata,
                        category_id=category_id,
                        category_name=category_name,
                    )
                    log_classification(cursor, transaction_id, payload)

                # Accumulate debug details if requested (useful for testing/tracing).
                if debug:
                    classifications.append(
                        {
                            "note": note,
                            "normalized_note": normalized_note,
                            "amount": amount,
                            "category_id": category_id,
                            "category_name": category_name,
                            "phase": metadata.get("phase"),
                            "resolution_path": metadata.get("resolution_path"),
                            "matched_keyword": metadata.get("matched_keyword"),
                            "match_type": metadata.get("match_type"),
                            "priority": metadata.get("priority"),
                        }
                    )

            # All rows successfully inserted and logged. Commit the transaction.
            db_conn.commit()
        observability_summary = record_import_metrics(
            # Record metrics for observability: latency, failure rate, phase 3 fallback rate (monitored 1h rolling window).
            latency_seconds=perf_counter() - started_at,
            classification_failed=classification_failed,
            attempted_rows=attempted_rows,
            phase3_rows=phase3_rows,
        )
        if debug:
            return {
                "inserted": inserted_count,
                "classifications": classifications,
                "cache_meta": cache_meta,
                "merchant_normalization_enabled": runtime_flags["merchant_normalization_enabled"],
                "observability": observability_summary,
            }
        return {"inserted": inserted_count}

    except HTTPException:
        record_import_metrics(
            latency_seconds=perf_counter() - started_at,
            classification_failed=classification_failed,
            attempted_rows=attempted_rows,
            phase3_rows=phase3_rows,
        )
        raise
    except Exception as e:
        record_import_metrics(
            latency_seconds=perf_counter() - started_at,
            classification_failed=classification_failed,
            attempted_rows=attempted_rows,
            phase3_rows=phase3_rows,
        )
        raise HTTPException(status_code=500, detail=f"Failed to import transactions: {str(e)}")

def parse_csv(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse CSV file using pandas"""
    try:
        df = pd.read_csv(io.BytesIO(file_content), dtype=str)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

def parse_excel(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse Excel file using pandas"""
    try:
        df = pd.read_excel(io.BytesIO(file_content), dtype=str)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel: {str(e)}")

def parse_json(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse JSON file"""
    try:
        text = file_content.decode('utf-8')
        data = json.loads(text)

        # Handle different JSON structures
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if 'transactions' in data and isinstance(data['transactions'], list):
                return data['transactions']
            else:
                return [data]
        else:
            raise ValueError("Unexpected JSON structure")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse JSON: {str(e)}")

def parse_text(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse text file (tab or comma separated)"""
    try:
        text = file_content.decode('utf-8')
        lines = [line.strip() for line in text.replace('\r', '').split('\n') if line.strip()]

        if not lines:
            return []

        # Detect delimiter
        first_line = lines[0]
        if '\t' in first_line:
            delimiter = '\t'
        else:
            delimiter = ','

        # Parse headers
        headers = [h.strip() for h in first_line.split(delimiter)]
        data_lines = lines[1:]

        result = []
        for line in data_lines:
            values = [v.strip() for v in line.split(delimiter)]
            row = {}
            for i, header in enumerate(headers):
                row[header] = values[i] if i < len(values) else ""
            result.append(row)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse text: {str(e)}")

def parse_date(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize date fields in the data - handle both date and datetime formats"""
    date_patterns = [
        '%Y-%m-%d %H:%M:%S.%f',  # datetime with microseconds
        '%Y-%m-%d %H:%M:%S',     # datetime with seconds
        '%Y-%m-%d %H:%M',        # datetime without seconds
        '%Y-%m-%dT%H:%M:%S.%fZ', # ISO datetime with microseconds UTC
        '%Y-%m-%dT%H:%M:%S.%f',  # ISO datetime with microseconds
        '%Y-%m-%dT%H:%M:%SZ',    # ISO datetime UTC
        '%Y-%m-%dT%H:%M:%S',     # ISO datetime
        '%Y-%m-%dT%H:%M',        # ISO datetime without seconds
        '%Y-%m-%d',              # date only
        '%d/%m/%Y %H:%M:%S',     # dd/mm/yyyy hh:mm:ss
        '%d/%m/%Y %I:%M:%S %p',  # dd/mm/yyyy hh:mm:ss AM/PM
        '%d/%m/%Y',              # dd/mm/yyyy
        '%m-%d-%Y',              # mm-dd-yyyy
        '%m/%d/%Y',              # mm/dd/yyyy
        '%d-%m-%Y',              # dd-mm-yyyy
        '%m/%d/%Y %H:%M:%S',     # mm/dd/yyyy hh:mm:ss
        '%m/%d/%Y %I:%M:%S %p',  # mm/dd/yyyy hh:mm:ss AM/PM
        '%B %d, %Y',             # Month dd, yyyy
        '%b %d, %Y',             # Mon dd, yyyy
        '%d %B %Y',              # dd Month yyyy
        '%d %b %Y',              # dd Mon yyyy
    ]

    def looks_like_date(value: str) -> bool:
        if not isinstance(value, str):
            return False
        # Check for various date/datetime patterns
        patterns = [
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z',  # ISO with milliseconds UTC
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}',   # ISO with microseconds
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',        # ISO UTC
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',          # ISO datetime
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',                # ISO datetime no seconds
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',          # datetime with seconds
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}',                # datetime no seconds
            r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',                  # dd/mm/yyyy or mm/dd/yyyy
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',                  # yyyy/mm/dd
            r'\d{4}-\d{2}-\d{2}',                            # date only
            r'\w{3,9} \d{1,2}, \d{4}',                       # Month dd, yyyy
            r'\d{1,2} \w{3,9} \d{4}',                        # dd Month yyyy
        ]
        return any(re.search(pattern, value) for pattern in patterns)

    def try_parse_date(value: str) -> str:
        if not isinstance(value, str):
            return str(value)

        # First try exact matches with known patterns
        for pattern in date_patterns:
            try:
                dt = datetime.strptime(value.strip(), pattern)
                # Fix 2-digit years
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                # Always return date only (no time)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # If no exact match, try to extract date-like substrings
        # Look for patterns like YYYY-MM-DD, MM/DD/YYYY, etc.
        date_extract_patterns = [
            (r'\d{4}-\d{2}-\d{2}', '%Y-%m-%d'),              # YYYY-MM-DD
            (r'\d{1,2}/\d{1,2}/\d{4}', '%m/%d/%Y'),         # MM/DD/YYYY
            (r'\d{1,2}-\d{1,2}-\d{4}', '%m-%d-%Y'),         # MM-DD-YYYY
            (r'\d{4}/\d{1,2}/\d{1,2}', '%Y/%m/%d'),         # YYYY/MM/DD
        ]

        for regex, fmt in date_extract_patterns:
            match = re.search(regex, value)
            if match:
                try:
                    dt = datetime.strptime(match.group(), fmt)
                    if dt.year < 100:
                        dt = dt.replace(year=dt.year + 2000)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue

        # If still no match, return original value
        return value

    result = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            if isinstance(value, str) and looks_like_date(value):
                new_row[key] = try_parse_date(value)
            else:
                new_row[key] = value
        result.append(new_row)

    return result

@app.post("/parse")
async def parse_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Parse uploaded file and return normalized data"""
    try:
        # Read file content
        content = await file.read()
        filename = file.filename or "unknown"

        # Detect file type
        if filename.lower().endswith('.csv'):
            file_type = 'csv'
            rows = parse_csv(content)
        elif filename.lower().endswith(('.xlsx', '.xls')):
            file_type = 'excel'
            rows = parse_excel(content)
        elif filename.lower().endswith('.json'):
            file_type = 'json'
            rows = parse_json(content)
        elif filename.lower().endswith('.txt'):
            file_type = 'text'
            rows = parse_text(content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # Apply date parsing
        normalized_rows = parse_date(rows)

        return {
            "filename": filename,
            "fileType": file_type,
            "rows": normalized_rows
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)