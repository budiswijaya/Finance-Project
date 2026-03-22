# Testing

## Current State

- Frontend: manual testing workflow, no frontend test runner configured in `package.json`.
- Backend category-classification: automated unit tests are present.

## Backend Automated Tests

- Test file: `test_category_keywords.py`
- Scope: imports production classifier (`backend/category_classifier.py`) and validates runtime behavior.
- Current suite size: 9 unit tests.

### Covered Behaviors

1. Keyword priority resolution
2. Deterministic tie-break by category ID
3. Word-boundary matching and embedded-substring rejection
4. Exact matching behavior
5. Category-name fallback across all categories
6. Income keywords can classify negative amounts
7. Expense keywords can classify positive amounts
8. Error guidance includes global keyword/category options
9. Metadata path reporting for fallback classification

### Run Command

```bash
cd /d/Github/Finance-Project/Dashboard/DashboardV1
d:/Github/.venv/Scripts/python.exe test_category_keywords.py
```

## Manual Testing Workflow

1. Upload a source file and verify original grid render.
2. Map columns and append normalized data.
3. Edit cells and verify undo/redo behavior.
4. Run Calculate and verify validation summary.
5. Submit to backend and verify inserted count response.
6. Save/load normalized state from local storage.

## Backend Endpoint Checks

- `GET /health`
- `POST /parse`
- `GET /categories/types`
- `POST /transactions/import`
- `POST /transactions/import?debug=true`
- `GET /category-keywords`
- `POST /category-keywords`
- `PUT /category-keywords/{keyword_id}`
- `DELETE /category-keywords/{keyword_id}`
- `POST /category-keywords/validate-note`
- `GET /category-keywords/coverage`

## Regression Focus Areas

- Deterministic category assignment regardless of amount sign
- Keyword priority and deterministic tie-break behavior
- Category-name fallback after keyword miss
- Date normalization to `YYYY-MM-DD`
- Amount parsing edge cases (currency symbols, negatives, parentheses)
