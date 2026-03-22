from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List, Dict, Any, Optional
import pandas as pd
import json
import csv
import io
from datetime import datetime
import re
from collections import Counter

import psycopg2

import os
from pathlib import Path
from dotenv import load_dotenv
from category_classifier import determine_category_id
from classification_observability import build_log_payload

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")  # Keep fallback for now
)

app = FastAPI(title="Data Parser API", version="1.0.0")

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
        cursor = conn.cursor()
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

@app.get("/categories/types")
async def get_category_types():
    """Get distinct category types (income, expense)"""
    try:
        cursor = conn.cursor()
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
    keyword_columns = get_table_columns(cursor, "category_keywords")
    has_match_type = "match_type" in keyword_columns
    has_is_active = "is_active" in keyword_columns

    match_type_select = "COALESCE(ck.match_type, 'substring')" if has_match_type else "'substring'"
    active_filter = "AND COALESCE(ck.is_active, TRUE) = TRUE" if has_is_active else ""

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

    categories = cursor.fetchall()
    keywords_by_type = {"income": {}, "expense": {}}
    category_names_by_type = {"income": {}, "expense": {}}
    available_category_names_by_type = {"income": [], "expense": []}
    category_lookup = {}

    for cat_id, cat_name, cat_type, keywords_json in categories:
        if cat_type not in keywords_by_type:
            continue

        normalized_name = cat_name.lower().strip()
        category_names_by_type[cat_type][normalized_name] = cat_id
        available_category_names_by_type[cat_type].append(cat_name)
        category_lookup[cat_id] = {"name": cat_name, "type": cat_type}

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

        if cleaned_keywords:
            keywords_by_type[cat_type][cat_id] = cleaned_keywords

    return keywords_by_type, category_names_by_type, available_category_names_by_type, category_lookup


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

        cursor = conn.cursor()
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
        cursor = conn.cursor()

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
        conn.commit()

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
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create category keyword: {str(e)}")


@app.put("/category-keywords/{keyword_id}")
async def update_category_keyword(keyword_id: int, payload: Dict[str, Any]):
    """Update an existing keyword rule."""
    try:
        cursor = conn.cursor()
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
        conn.commit()

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
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update category keyword: {str(e)}")


@app.delete("/category-keywords/{keyword_id}", status_code=204)
async def delete_category_keyword(keyword_id: int):
    """Soft-delete one keyword rule by marking it inactive."""
    try:
        cursor = conn.cursor()
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

        conn.commit()
        return Response(status_code=204)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
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

        cursor = conn.cursor()
        keywords_by_type, category_names_by_type, available_category_names_by_type, category_lookup = load_category_context(cursor)
        category_id, metadata = determine_category_id(
            amount=amount,
            note=note,
            keywords_by_type=keywords_by_type,
            category_names_by_type=category_names_by_type,
            available_category_names_by_type=available_category_names_by_type,
            return_metadata=True,
        )

        if category_id is None:
            return {"classification_scope": "global", "classification": metadata}

        return {
            "classification_scope": "global",
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

        cursor = conn.cursor()
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


@app.post("/transactions/import")
async def import_transactions(rows: List[Dict[str, Any]], debug: bool = Query(default=False)):
    """Import transactions with deterministic category assignment."""
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM categories")
        category_count = cursor.fetchone()[0]
        if category_count == 0:
            raise HTTPException(
                status_code=400,
                detail="You should define categories in database first to submit data.",
            )

        keywords_by_type, category_names_by_type, available_category_names_by_type, category_lookup = load_category_context(cursor)
        logging_enabled = is_classification_log_available(cursor)

        inserted_count = 0
        classifications = []

        for r in rows:
            if not r.get("date"):
                raise HTTPException(status_code=400, detail=f"Date is required for transaction: {r}")

            amount = r.get("amount")
            if amount is None or not isinstance(amount, (int, float)):
                raise HTTPException(status_code=400, detail=f"Valid amount is required for transaction: {r}")

            note = r.get("note") or r.get("description") or ""
            category_id, metadata = determine_category_id(
                amount=amount,
                note=note,
                keywords_by_type=keywords_by_type,
                category_names_by_type=category_names_by_type,
                available_category_names_by_type=available_category_names_by_type,
                return_metadata=True,
            )

            if category_id is None:
                raise HTTPException(status_code=400, detail=metadata.get("error_message"))

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

            category_name = category_lookup.get(category_id, {}).get("name")
            transaction_type = "income" if amount > 0 else "expense"

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

            if debug:
                classifications.append(
                    {
                        "note": note,
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

        conn.commit()
        if debug:
            return {"inserted": inserted_count, "classifications": classifications}
        return {"inserted": inserted_count}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
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