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
                1: [("salary", 1)],
            },
            "expense": {
                3: [("cafe", 1), ("coffee", 1), ("indomaret", 2)],
                5: [("grab", 2), ("taxi", 1)],
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

    def test_keyword_priority_wins(self):
        category_id = self.classify(-25.0, "cafe grab lunch")
        self.assertEqual(category_id, 3)

    def test_tie_breaker_uses_lower_category_id(self):
        self.keywords_by_type["expense"][3] = [("alpha", 1)]
        self.keywords_by_type["expense"][5] = [("alpha", 1)]
        category_id = self.classify(-10.0, "alpha purchase")
        self.assertEqual(category_id, 3)

    def test_fallback_category_name_scoped_to_type(self):
        # "salary" exists only in income type and should not classify an expense.
        with self.assertRaises(HTTPException) as context:
            self.classify(-100.0, "salary correction")

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("type: expense", context.exception.detail)

    def test_income_keyword_does_not_match_expense_flow(self):
        # Regression guard: positive-only keyword must not classify negative amount.
        with self.assertRaises(HTTPException):
            self.classify(-40.0, "salary reimbursement")

    def test_error_lists_type_scoped_options(self):
        with self.assertRaises(HTTPException) as context:
            self.classify(50.0, "unknown income source")

        self.assertIn("type: income", context.exception.detail)
        self.assertIn("salary", context.exception.detail.lower())
        self.assertNotIn("cafe", context.exception.detail.lower())


if __name__ == "__main__":
    unittest.main()
