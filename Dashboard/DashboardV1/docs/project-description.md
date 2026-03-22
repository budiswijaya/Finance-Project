# Project Description

## Purpose

Finance Dashboard normalizes imported transaction files and submits validated rows to a backend that performs deterministic category classification and persistence.

## Current Scope

- Frontend: file parsing UX, column mapping, normalized grid editing, submission workflow.
- Backend: category classification, rule management, import transaction persistence, and classification diagnostics.

## Classification Model (Current)

- Strategy is rule-based and deterministic.
- Matching is global across categories (not scoped by amount sign).
- Three-stage resolution:
  1. Keyword match (`substring`, `word_boundary`, `exact`)
  2. Category-name fallback
  3. HTTP 400 with guidance

## API Surface

### Core
- `GET /health`
- `POST /parse`
- `GET /categories`
- `GET /categories/types`
- `POST /transactions/import`

### Keyword Rule Lifecycle
- `GET /category-keywords`
- `POST /category-keywords`
- `PUT /category-keywords/{id}`
- `DELETE /category-keywords/{id}`
- `POST /category-keywords/validate-note`
- `GET /category-keywords/coverage`

## Data Model Highlights

- `categories`
- `transactions`
- `category_keywords` (`match_type`, `is_active`, audit columns)
- `transaction_classification_log` (observability)

## Operational Notes

- Schema bootstrap: `backend/database_setup.sql` (idempotent).
- Environment template: `backend/.env.example`.
- Local runtime env: `backend/.env`.
- Backend startup reads env by script-relative path to avoid cwd issues.

## Testing

- Backend classifier tests: `test_category_keywords.py`.
- Suite currently validates mixed match types, deterministic tie-breaks, global fallback behavior, and metadata outputs.
