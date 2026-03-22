import hashlib
from typing import Any, Dict


def hash_note(note: str) -> str:
    """Hash note content to reduce plain-text storage in observability logs."""
    return hashlib.sha256((note or "").encode("utf-8")).hexdigest()


def build_log_payload(
    note: str,
    amount: float,
    transaction_type: str,
    metadata: Dict[str, Any],
    category_id: int,
    category_name: str,
) -> Dict[str, Any]:
    """Normalize classifier metadata into a log row payload."""
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
