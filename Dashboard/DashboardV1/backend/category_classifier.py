from typing import Dict, List, Tuple

from fastapi import HTTPException


def determine_category_id(
    amount: float,
    note: str,
    keywords_by_type: Dict[str, Dict[int, List[Tuple[str, int]]]],
    category_names_by_type: Dict[str, Dict[str, int]],
    available_category_names_by_type: Dict[str, List[str]],
) -> int:
    """
    Classify a transaction by transaction type first, then by keyword/name matching.

    Priority rules are deterministic: lower priority number wins, then lower category ID.
    """
    transaction_type = "income" if amount > 0 else "expense"
    note_lower = note.lower().strip()

    typed_keywords = keywords_by_type.get(transaction_type, {})
    typed_category_names = category_names_by_type.get(transaction_type, {})
    typed_available_categories = available_category_names_by_type.get(transaction_type, [])

    # Phase 1: Keyword matching within the derived transaction type.
    available_keywords = {}
    for category_id, keywords_list in typed_keywords.items():
        for keyword, priority in keywords_list:
            if keyword in note_lower:
                if category_id not in available_keywords or priority < available_keywords[category_id][1]:
                    available_keywords[category_id] = (keyword, priority)

    if available_keywords:
        best_match = min(available_keywords.items(), key=lambda x: (x[1][1], x[0]))
        return best_match[0]

    # Phase 2: Category name fallback, still within the derived type.
    for category_name, category_id in typed_category_names.items():
        if category_name in note_lower:
            return category_id

    # Phase 3: Error guidance scoped to the derived type only.
    all_keywords = []
    for _, keywords_list in typed_keywords.items():
        for keyword, _ in keywords_list:
            all_keywords.append(keyword)

    keywords_str = ", ".join(sorted(set(all_keywords))) if all_keywords else "(none defined)"
    categories_str = ", ".join(typed_available_categories) if typed_available_categories else "(none defined)"
    raise HTTPException(
        status_code=400,
        detail=(
            f"Cannot automatically determine category for '{note}' (type: {transaction_type}). "
            f"Available keywords: {keywords_str}. "
            f"You can also include a category name like {categories_str} in the note."
        ),
    )
