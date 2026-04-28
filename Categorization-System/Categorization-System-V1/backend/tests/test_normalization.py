import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


def test_apply_normalization_rule_exact():
    assert main._apply_normalization_rule("mcdonalds", "mcdonalds", "restaurant", "exact") == "restaurant"
    assert main._apply_normalization_rule("mcdonalds #123", "mcdonalds", "restaurant", "exact") == "mcdonalds #123"


def test_apply_normalization_rule_word_boundary():
    original = "mcdonalds #123"
    normalized = main._apply_normalization_rule(original, "mcdonalds", "restaurant", "word_boundary")
    assert normalized == "restaurant #123"


def test_normalize_merchant_note_removes_trailing_ids_and_punctuation():
    rules = [
        {"pattern": "mcdonalds", "replacement": "mcdonalds", "match_type": "word_boundary"},
        {"pattern": "#", "replacement": "", "match_type": "substring"},
    ]

    assert main.normalize_merchant_note("MCDONALDS #123", rules) == "mcdonalds"


def test_determine_category_id_with_normalized_note():
    amount = -15.75
    note = "mcdonalds"
    keywords_by_type = {"expense": {1: [("mcdonalds", 1, "exact")]}}
    category_names_by_type = {"expense": {"food & dining": 1}}
    available_category_names_by_type = {"expense": ["Food & Dining"]}

    category_id, metadata = main.determine_category_id(
        amount=amount,
        note=note,
        keywords_by_type=keywords_by_type,
        category_names_by_type=category_names_by_type,
        available_category_names_by_type=available_category_names_by_type,
        return_metadata=True,
    )

    assert category_id == 1
    assert metadata["phase"] == 1
    assert metadata["matched_keyword"] == "mcdonalds"
    assert metadata["match_type"] == "exact"
    assert metadata["priority"] == 1
