from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from word_boundary_matcher import matches_word_boundary


KeywordRule = Tuple[str, int, str]


def _normalize_rule(rule: Tuple[Any, ...]) -> Optional[KeywordRule]:
    """Normalize legacy and Phase 2 keyword tuples into a single shape."""
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


def _matches_keyword(note_lower: str, keyword: str, match_type: str) -> bool:
    """Apply one matching strategy based on rule type."""
    if match_type == "exact":
        return note_lower == keyword
    if match_type == "word_boundary":
        return matches_word_boundary(note_lower, keyword)
    return keyword in note_lower


def determine_category_id(
    amount: float,
    note: str,
    keywords_by_type: Dict[str, Dict[int, List[Tuple[Any, ...]]]],
    category_names_by_type: Dict[str, Dict[str, int]],
    available_category_names_by_type: Dict[str, List[str]],
    return_metadata: bool = False,
) -> Any:
    """
    Classify a transaction with deterministic keyword/name matching.

    Priority rules are deterministic: lower priority number wins, then lower category ID.
    """
    note_lower = note.lower().strip()

    # Phase 2 override: do not scope classification by amount sign.
    all_keywords = {}
    for scoped_keywords in keywords_by_type.values():
        for category_id, keyword_rules in scoped_keywords.items():
            all_keywords.setdefault(category_id, []).extend(keyword_rules)

    all_category_names = {}
    for scoped_names in category_names_by_type.values():
        all_category_names.update(scoped_names)

    all_available_categories = []
    for scoped_available in available_category_names_by_type.values():
        all_available_categories.extend(scoped_available)

    # Phase 1: Keyword matching across all categories.
    available_keywords = {}
    for category_id, keywords_list in all_keywords.items():
        for raw_rule in keywords_list:
            normalized_rule = _normalize_rule(raw_rule)
            if not normalized_rule:
                continue

            keyword, priority, match_type = normalized_rule
            if _matches_keyword(note_lower, keyword, match_type):
                if category_id not in available_keywords or priority < available_keywords[category_id][1]:
                    available_keywords[category_id] = (keyword, priority, match_type)

    if available_keywords:
        best_match = min(available_keywords.items(), key=lambda x: (x[1][1], x[0]))
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

    # Phase 2: Category name fallback across all categories.
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

    # Phase 3: Error guidance from the global rule set.
    all_available_keywords = []
    for _, keywords_list in all_keywords.items():
        for raw_rule in keywords_list:
            normalized_rule = _normalize_rule(raw_rule)
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
