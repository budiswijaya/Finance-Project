#!/usr/bin/env python3
"""
Unit tests for production category classification logic.

Usage:
    python test_category_keywords.py
"""

import sys
import unittest
from pathlib import Path

from fastapi import HTTPException

# Import production classifier module from backend/.
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from category_classifier import determine_category_id  # noqa: E402


class TestCategoryKeywords(unittest.TestCase):
    def setUp(self):
        self.keywords_by_type = {
            "income": {
                1: [("salary", 1, "substring")],
            },
            "expense": {
                3: [("cafe", 1, "substring"), ("coffee", 1, "word_boundary"), ("indomaret", 2, "substring")],
                5: [("grab", 2, "substring"), ("taxi", 1, "exact")],
            },
        }
        self.category_names_by_type = {
            "income": {
                "salary": 1,
                "freelance": 2,
            },
            "expense": {
                "food & dining": 3,
                "transportation": 5,
            },
        }
        self.available_category_names_by_type = {
            "income": ["Salary", "Freelance"],
            "expense": ["Food & Dining", "Transportation"],
        }

    def classify(self, amount: float, note: str) -> int:
        return determine_category_id(
            amount=amount,
            note=note,
            keywords_by_type=self.keywords_by_type,
            category_names_by_type=self.category_names_by_type,
            available_category_names_by_type=self.available_category_names_by_type,
        )

    def classify_with_meta(self, amount: float, note: str):
        return determine_category_id(
            amount=amount,
            note=note,
            keywords_by_type=self.keywords_by_type,
            category_names_by_type=self.category_names_by_type,
            available_category_names_by_type=self.available_category_names_by_type,
            return_metadata=True,
        )

    def test_keyword_priority_wins(self):
        category_id = self.classify(-25.0, "cafe grab lunch")
        self.assertEqual(category_id, 3)

    def test_tie_breaker_uses_lower_category_id(self):
        self.keywords_by_type["expense"][3] = [("alpha", 1, "substring")]
        self.keywords_by_type["expense"][5] = [("alpha", 1, "substring")]
        category_id = self.classify(-10.0, "alpha purchase")
        self.assertEqual(category_id, 3)

    def test_word_boundary_blocks_embedded_match(self):
        category_id, metadata = self.classify_with_meta(-11.0, "coffee-break")
        self.assertEqual(category_id, 3)
        self.assertEqual(metadata["match_type"], "word_boundary")

        category_id, metadata = self.classify_with_meta(-11.0, "StarbucksCoffee")
        self.assertIsNone(category_id)
        self.assertEqual(metadata["phase"], 3)

    def test_exact_match_requires_whole_note(self):
        category_id, metadata = self.classify_with_meta(-7.0, "taxi")
        self.assertEqual(category_id, 5)
        self.assertEqual(metadata["match_type"], "exact")

        category_id, metadata = self.classify_with_meta(-7.0, "taxi ride")
        self.assertIsNone(category_id)
        self.assertEqual(metadata["phase"], 3)

    def test_fallback_category_name_not_scoped_by_type(self):
        category_id = self.classify(-100.0, "salary correction")
        self.assertEqual(category_id, 1)

    def test_income_keyword_can_match_negative_amount(self):
        category_id = self.classify(-40.0, "salary reimbursement")
        self.assertEqual(category_id, 1)

    def test_expense_keyword_can_match_positive_amount(self):
        category_id = self.classify(500.0, "cafepoint")
        self.assertEqual(category_id, 3)

    def test_error_lists_unscoped_options(self):
        with self.assertRaises(HTTPException) as context:
            self.classify(50.0, "unknown income source")

        self.assertIn("salary", context.exception.detail.lower())
        self.assertIn("cafe", context.exception.detail.lower())

    def test_metadata_path_for_category_name_fallback(self):
        category_id, metadata = self.classify_with_meta(-30.0, "Food & Dining charge")
        self.assertEqual(category_id, 3)
        self.assertEqual(metadata["phase"], 2)
        self.assertEqual(metadata["resolution_path"], "category_name_match")


if __name__ == "__main__":
    unittest.main()
