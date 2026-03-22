# Category Keywords Enhancement - Consolidated Implementation Plan

**Status**: Implemented (Phase 1 + Phase 2 merged)
**Date**: March 22, 2026
**Owner**: Architecture
**Scope**: Backend classification, keyword lifecycle API, and observability

---

## 1. Executive Summary

This document is the canonical plan and implementation record for category classification improvements.

The system evolved from name-based fallback matching to a deterministic, rule-based classifier with:

1. Keyword-first classification with deterministic tie-break rules.
2. Mixed match modes (`substring`, `word_boundary`, `exact`).
3. Rule lifecycle endpoints (CRUD + soft delete).
4. Optional debug metadata and classification observability logging.

**Classification Scope Policy (Current)**:
- Matching is global across categories (not restricted by amount sign).
- Amount sign is still captured as `transaction_type` metadata for observability.

---

## 2. Implementation Status

### Phase 1 Foundation
- [x] Seed data moved to dynamic category lookup by name.
- [x] Deterministic priority + category-id tie-break behavior implemented.
- [x] Shared classifier module extracted (`backend/category_classifier.py`).
- [x] Idempotent DB setup for constraints and seed data.

### Phase 2 Enhancements
- [x] `match_type` support (`substring`, `word_boundary`, `exact`).
- [x] Rule lifecycle API:
  - `GET /category-keywords`
  - `POST /category-keywords`
  - `PUT /category-keywords/{id}`
  - `DELETE /category-keywords/{id}` (soft delete)
- [x] Diagnostic endpoints:
  - `POST /category-keywords/validate-note`
  - `GET /category-keywords/coverage`
- [x] Optional import debug output (`POST /transactions/import?debug=true`).
- [x] Optional `transaction_classification_log` persistence.

### Policy Adjustment (March 22, 2026)
- [x] Amount-sign type scoping removed for matching/fallback.
- [x] Keyword and category-name matching now run against global category context.

---

## 3. Files of Record

### Backend
- `backend/main.py`
- `backend/category_classifier.py`
- `backend/word_boundary_matcher.py`
- `backend/classification_observability.py`
- `backend/database_setup.sql`

### Documentation
- `docs/system_patterns.md`
- `docs/system_architectural.md`
- `docs/tech_context.md`
- `docs/testing.md`

### Tests
- `test_category_keywords.py`

---

## 4. Classification Behavior (Current)

### Phase 1: Keyword Match
- Evaluate active keyword rules from all categories.
- Apply per-rule strategy by `match_type`:
  - `substring`: keyword exists in note.
  - `word_boundary`: keyword matches token boundary.
  - `exact`: normalized note equals normalized keyword.
- Resolve candidates deterministically:
  1. Lowest `priority` wins.
  2. Lowest `category_id` breaks ties.

### Phase 2: Category Name Fallback
- If no keyword match exists, match category names by substring against the same global context.

### Phase 3: Error Guidance
- If still no match, return HTTP 400 with available keywords and categories.

---

## 5. API Contract

### Existing Endpoint (Enhanced)
- `POST /transactions/import`
- Default response remains unchanged:
```json
{ "inserted": 15 }
```
- Optional debug mode:
```json
{
  "inserted": 15,
  "classifications": [
    {
      "note": "cafe lunch",
      "amount": -25.5,
      "category_id": 4,
      "category_name": "Food & Dining",
      "phase": 1,
      "resolution_path": "keyword_match",
      "matched_keyword": "cafe",
      "match_type": "substring",
      "priority": 1
    }
  ]
}
```

### New Endpoints
- `GET /category-keywords`
- `POST /category-keywords`
- `PUT /category-keywords/{id}`
- `DELETE /category-keywords/{id}`
- `POST /category-keywords/validate-note`
- `GET /category-keywords/coverage`

---

## 6. Database Changes (Current)

### `category_keywords` extensions
- `match_type VARCHAR(20)` with check constraint.
- `is_active BOOLEAN` for soft delete.
- `created_by VARCHAR(255)`.
- `updated_at TIMESTAMP`.
- Indexes for active/priority lookup and normalized keyword lookup.

### New observability table
- `transaction_classification_log`
- Stores phase, resolution path, matched keyword/category, and note hash.

### Compatibility
- Setup SQL is idempotent and rerunnable.
- Legacy rules default to `match_type='substring'` and active status.

---

## 7. Testing Summary

- Automated classifier tests: `test_category_keywords.py` (9 tests, passing).
- Coverage includes:
  - Priority and tie-break determinism.
  - `word_boundary` behavior and embedded-substring rejection.
  - `exact` match behavior.
  - Global fallback behavior (unscoped by amount sign).
  - Metadata path assertions.

---

## 8. Trade-offs

- Deterministic rules over ML:
  - Pros: explainable, auditable, predictable.
  - Cons: manual rule maintenance and known lexical edge cases.
- Per-request rule snapshot loading:
  - Pros: consistent outcomes within one request.
  - Cons: no cache optimization yet.
- Soft delete for rules:
  - Pros: rollback/audit safety.
  - Cons: requires active filtering in all reads.

---

## 9. Cleanup and Source of Truth

- This file replaces standalone phase-only planning artifacts.
- `PHASE_2_IMPLEMENTATION_PLAN.md` is deprecated in favor of this consolidated plan.

---

## 10. Future Work

- Rule management UI in frontend.
- Rule versioning / change history.
- Coverage trend dashboards and retention policy automation.
- Optional merchant normalization layer before rule matching.

---

**Version**: 2.2 (Consolidated)
**Status**: Canonical plan for current implementation
