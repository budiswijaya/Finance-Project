# Testing

## Current State

- **Frontend**: Manual testing workflow; no frontend unit test runner configured in `package.json`.
- **Backend**: Standalone Python test scripts were removed on Mar 22, 2026 to simplify project maintenance (scripts were one-off proofs, not integrated into CI/npm).
- **Verification Baseline**: Build checks (`npm run build`, `python -m py_compile`) + manual smoke testing + API integration checks.

## Build Verification (Automated)

```bash
# Syntax check backend
python -m py_compile backend/main.py

# Build frontend
npm run build

# Lint frontend
npm run lint
```

All three should PASS on every workspace.

## Manual Smoke Test Workflow

This is the recommended quick verification process:

### 1. Backend Startup
```bash
cd backend
python main.py
```
- ✓ Database schema initializes if needed
- ✓ Service listens on `http://localhost:8003`
- ✓ Sample categories and keywords are seeded

### 2. Frontend Startup
```bash
npm run dev
```
- ✓ Vite dev server starts on `http://localhost:5173`
- ✓ Can load and inspect app (browser DevTools)

### 3. Core Workflow (UI)
1. Upload CSV/Excel file → Original grid renders with correct columns
2. Map columns (Date, Note, Amount) → Columns appear in normalized grid
3. Click Normalize → Data is appended to normalized grid
4. Edit a cell in normalized grid → Change is reflected
5. Undo/Redo (Ctrl+Z / Ctrl+Shift+Z) → Changes revert and reapply
6. Click Calculate → Totals are computed, red validation errors appear if invalid
7. Fix errors and Calculate again → Summary updates
8. Click Submit → Backend response shows transaction count and any classification failures
9. Admin panel: Toggle merchant normalization → Feature flag state changes
10. Admin panel: Create a keyword rule → Rule appears in list
11. Validate a test note → Classification result appears

### 4. Quick API Checks (curl / Postman)
```bash
# Health check
curl http://localhost:8003/health

# Parse a file
curl -X POST -F "file=@sample.csv" http://localhost:8003/parse

# Get categories
curl http://localhost:8003/categories

# Get keywords
curl http://localhost:8003/category-keywords

# Validate a note against current rules
curl -X POST http://localhost:8003/category-keywords/validate-note \
  -H "Content-Type: application/json" \
  -d '{"note": "Starbucks coffee"}'

# Test transaction import
curl -X POST http://localhost:8003/transactions/import \
  -H "Content-Type: application/json" \
  -d '{
    "transactions": [
      {"date": "2026-03-23", "note": "grocery store", "amount": -50.00}
    ]
  }'
```

## Regression Test Focus Areas

These are the core behaviors to verify in manual testing:

1. **Deterministic category assignment**
   - Same note + keywords should produce same category ID every time
   - Keyword priority (lower number wins)
   - Tie-break: lower category ID wins for equal priority
   
2. **Classification phases**
   - Keyword match → Category name fallback → HTTP 400 error if no match
   - Error response lists available keywords and category names
   
3. **Date normalization**
   - CSV dates: various formats (MM/DD/YYYY, DD-MON-YY, etc.) → YYYY-MM-DD
   - Excel dates: serial numbers → YYYY-MM-DD
   - Text dates: human-readable → YYYY-MM-DD
   
4. **Amount parsing**
   - Decimal amounts (1,234.56 or 1.234,56 regional)
   - Negatives (-123.45)
   - Currency symbols ($123.45)
   - Parentheses as negative (123.45) → -123.45
   
5. **Undo/Redo state management**
   - Stack maintains 100 states max
   - Undo then new action → redo stack clears
   - Serialize/deserialize through refs without re-render loops
   
6. **Soft-delete keyword rules**
   - Create keyword → appears in list
   - Delete keyword → marked `is_active=false` in DB
   - Deleted keyword excluded from classification
   - PUT to reactivate → keyword usable again
   
7. **Cache invalidation**
   - Write keyword rule → `classification_context_version` incremented
   - Cache rebuilt on next import
   - Empty cache with `POST /admin/classification-context/refresh` → forces rebuild
   
8. **Merchant normalization (when enabled)**
   - Feature flag ON → rules apply during import
   - Validate note: `POST /admin/merchant-normalization-rules/validate-note` → returns normalized note
   - Feature flag OFF → normalization skipped
   - Word-boundary rules use true `\b...\b` regex (not literal strings)
   
9. **Import observability (rolling 1-hour window)**
   - Classification failure rate > 10% (min 100 samples) → alert
   - Phase 3 fallback rate > 20% (min 100 samples) → investigate signal
   - Import latency > 1 second → warning
   - View via `GET /admin/observability/alerts`
   
10. **Save/load from localStorage**
    - Click Save (browser side) → data persists
    - Reload page → data restores with timestamp
    - Format mismatch → silent fail, user can continue

## Removed Test Scripts (Mar 22, 2026 Cleanup)

These standalone scripts were validated and then removed to reduce maintenance burden:

| Script | Coverage | Status | Reason Removed |
|--------|----------|--------|---|
| `test_category_keywords.py` | Deterministic rules, priority tie-breaks, fallback | PASS (9/9) | Not integrated into CI; complex mocking |
| `test_phase3_admin.py` | Feature flags, observability thresholds, cache | PASS (11/11) | Mocked integration harder to maintain |
| `test_soft_delete_fix.py` | Partial unique index, reactivation | PASS (3/3) | One-time schema validation (not regression) |
| `test_root_cause_proof.py` | Concurrency, cache coherence | PASS (3/3) | Narrow scope; proof intent satisfied |

**For future integration testing**, consider:
- pytest + fixtures for backend API tests
- pytest-asyncio for async endpoint tests
- React Testing Library for frontend component tests
- CI/CD pipeline (GitHub Actions) for automated gate checks

## Validation Checklist (Before Deployment)

- ☐ `python -m py_compile backend/main.py` passes
- ☐ `npm run lint` passes (no ESLint errors)
- ☐ `npm run build` produces `dist/` folder
- ☐ Manual smoke test workflow completes without errors
- ☐ At least one file upload → normalization → submit roundtrip works end-to-end
- ☐ Keyword validation (`/category-keywords/validate-note`) returns category for current rules
- ☐ Feature flag toggle (`/admin/feature-flags/merchant-normalization`) changes state
- ☐ Save local state and reload page → data persists
