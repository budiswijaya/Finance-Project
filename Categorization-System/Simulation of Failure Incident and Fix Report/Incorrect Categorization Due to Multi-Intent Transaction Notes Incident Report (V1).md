# Incident Report: Incorrect Categorization Due to Multi-Intent Transaction Notes

**Project:** Data Normalization & Categorization Engine Version 1
**Date:** 2026-04-28
**Reporter:** Tester

---

## 1. Executive Summary

A production classification pipeline assigned transaction notes to the wrong category without throwing an error. This is a silent logical failure because the system behaved normally, but the business result was wrong.

A transaction note such as `GRABFOOD * MCDONALDS 123 SINGAPORE` was classified as `Transportation` because the deterministic keyword matcher selected the first operational keyword it found (`grab`) instead of capturing the stronger dining intent from `mcdonalds` and `food`.

---

## 2. Problem Statement

This incident is not a system crash or an API failure. It is a misclassification that passes validation and persists to the database.

The backend classifier treats each keyword independently and resolves ties using static priority/category ordering. That makes it blind to mixed-intent merchant notes containing transportation and food context simultaneously.

---

## 3. System Context

The version 1 system consists of:

- Frontend: React + Vite editor workflow
- Backend: FastAPI service in `backend/main.py`
- Database: PostgreSQL schema in `backend/database_setup.sql`

Key backend logic:

- `POST /transactions/import?debug=true` for import and debug classification
- `determine_category_id(...)` for keyword-based category selection
- `category_keywords` for rule storage and priority scoring

---

## 4. Impact

- User transactions are silently assigned to the wrong spending category.
- Monthly spending analytics become inaccurate.
- Budget alerts and financial reports may be misleading.
- User trust degrades because the system appears to work, but the numbers are wrong.

This type of failure is especially dangerous because no exception is raised, so support and observers may not notice it until analytics drift is significant.

---

## 5. Realistic Reproduction Input

Support should reproduce this with real bank-style notes, not toy examples.

```json
[
  {
    "date": "2026-04-20",
    "note": "GRABFOOD * MCDONALDS 123 SINGAPORE",
    "amount": -12.5
  }
]
```

Or a second real-world variant:

```json
[
  {
    "date": "2026-04-20",
    "note": "GRAB * MCDONALDS DELIVERY",
    "amount": -14.2
  }
]
```

These inputs contain:

- prefix tokens such as `GRABFOOD *`
- location/transaction suffixes such as `123 SINGAPORE`
- mixed intent signals: `grab` + `mcdonalds` + `food`

---

## 6. Actual Classification Output

Use the debug endpoint to capture the real behavior.

**Request:**

```bash
curl.exe -X POST "https://data-normalization-and-categorization.onrender.com/transactions/import?debug=true" \
  -H "Content-Type: application/json" \
  -d '[{"date":"2026-04-20","note":"GRABFOOD * MCDONALDS 123 SINGAPORE","amount":-12.50}]'
```

**Observed result (example):**

```json
{
  "inserted": 0,
  "classifications": [
    {
      "note": "grabfood * mcdonalds 123 singapore",
      "matched_keyword": "grab",
      "category": "Transportation",
      "phase": 1,
      "match_type": "substring",
      "priority": 2,
      "classification_status": "silent_misclassification"
    }
  ],
  "merchant_normalization_enabled": false,
  "observability": {
    "classification_failure_rate": 0.0,
    "phase3_fallback_rate": 0.0
  }
}
```

**Why this is a silent failure:**

- The service responded normally.
- The classification engine returned a category.
- The selected category was wrong for the user.

---

## 7. Root Cause Analysis

### What the system does

- It normalizes the note to lowercase.
- It finds matching keywords from `category_keywords`.
- It selects a category based on static priority and category ordering.
- It stops after the first best keyword match per category.

### What the system ignores

- the semantic grouping that `grabfood` is food-related
- the stronger dining signal from `mcdonalds`
- the fact that `food` context likely outweighs the transportation intent in a delivery note

### Core root cause

The classifier treats keywords as independent tokens and does not evaluate combined intent or relative semantic strength.

This means it can choose a lower-priority transportation keyword (`grab`) over a stronger food-related signal when both appear in a single note.

---

## 8. Evidence Layers

### A. DB evidence

Run this query to inspect the existing keyword priorities:

```sql
SELECT category_id, keyword, priority, match_type, is_active
FROM category_keywords
WHERE LOWER(keyword) IN ('grab', 'mcdonalds', 'restaurant', 'grabfood')
ORDER BY priority ASC, category_id ASC;
```

Example results:

| category_id | keyword    | priority | match_type    | is_active |
| ----------- | ---------- | -------- | ------------- | --------- |
| 4           | restaurant | 1        | substring     | true      |
| 3           | mcdonalds  | 1        | word_boundary | true      |
| 2           | grab       | 2        | substring     | true      |

If the system has no `grabfood` rule, the note is reduced to independent tokens and the transportation keyword wins.

### B. Debug evidence

The debug response should show the matched keywords and final selection.

Example matched keywords:

```json
{
  "matched_keywords": ["grab", "mcdonalds"],
  "selected_keyword": "grab",
  "selected_category": "Transportation",
  "selected_priority": 2,
  "ignored_keywords": ["mcdonalds"],
  "phase": 1
}
```

This shows the actual decision point: the system saw both signals but chose the wrong one.

### C. Observability evidence

A real incident can show a pattern in import metrics rather than a single failure.

Simulate multiple transactions and observe a spike in wrong categories:

- 30% of food/delivery notes classified as `Transportation`
- increased phase 1 matches on `grab`
- unremarked `classification_failure_rate` remains low

A practical alert scenario:

- `classification_failure_rate`: 0.0%
- `phase3_fallback_rate`: 0.0%
- but the `transactions` table shows a growing number of `Transportation` rows from food delivery

This is the exact point where observability is weak: the system appears healthy, but business outcomes degrade.

---

## 9. Why this is dangerous

This is not just a wrong category.

Silent misclassification causes:

- incorrect spending analytics
- misleading financial insights
- misreported budgets in `Food & Dining` vs `Transportation`
- loss of user trust when reports do not match actual receipts
- downstream errors in dashboards and alerts

That is the business impact of a silent logical failure.

---

## 10. Proposed Fixes

### Option 1 — Domain rule fix

Add merchant-specific rules for combined tokens and delivery contexts:

- `grabfood` → `Food & Dining`
- `grabfood mcdonalds` → `Food & Dining`
- `grab * mcdonalds delivery` → `Food & Dining`

This is the fastest fix and works well for the current rule engine.

### Option 2 — Priority tuning

Make food-related keywords higher priority than transportation keywords when both appear in a note.

Example:

- `restaurant` priority 1
- `mcdonalds` priority 1
- `grab` priority 3

This reduces the chance that `grab` wins over stronger dining signals.

### Option 3 — Multi-match scoring (advanced)

Improve classification by scoring all matched keywords together rather than selecting one keyword early.

A scoring model could consider:

- keyword priority
- semantic type weighting (food vs transportation)
- number of matched keywords per category
- matched phrase length and specificity

Then choose the category with the strongest aggregate score.

### Option 4 — Observability improvement

Log decision context for every classification:

- `all_matched_keywords`
- `final_decision`
- `confidence_score`
- `category_scores`
- `tie_break_info`

This would make silent logical failures detectable and easier to investigate.

---

## 11. Recommended Next Steps

1. Reproduce with real bank-style notes like `GRABFOOD * MCDONALDS 123 SINGAPORE`.
2. Inspect current `category_keywords` priority data for `grab`, `mcdonalds`, and `restaurant`.
3. Add targeted rules for `grabfood` and delivery token combinations.
4. Add a regression test covering multi-intent notes.
5. Improve debug output so the system reports all matched keywords and the selected category.
6. Add observability metrics for `silent_text_misclassifications` or `multi-intent keyword conflicts`.

---

## 12. Incident Summary

**Title:** Incorrect Categorization Due to Multi-Intent Transaction Notes

**Summary:** Transactions containing both transportation and food-related keywords were incorrectly classified due to deterministic keyword matching.

**Root Cause:** Classifier lacks contextual understanding and prioritizes keywords based on static rules rather than semantic intent.

**Impact:** Users see incorrect spending categories, leading to inaccurate reports.

**Fix:** Introduce merchant-specific rules and improve keyword prioritization; add richer observability for matched keywords.

---

## 13. Final Insight

This incident is not about syntax, API, or DB failure.

It is about system behavior vs business expectation.

The correct portfolio takeaway is: this is a silent data corruption risk caused by rule-based classifier design, not a standard server bug.
