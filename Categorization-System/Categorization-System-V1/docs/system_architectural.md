# System Architectural

## Overview

- Architecture style: React SPA frontend + FastAPI backend + PostgreSQL.
- Frontend responsibility: parse preview, normalize data, and submit transaction rows.
- Backend responsibility: classification, validation, persistence, and rule lifecycle APIs.
- Classification logic is centralized in backend for deterministic behavior.

## Runtime Topology

- Frontend dev server: `http://localhost:5173`
- Backend API: `http://localhost:8003`
- Database: PostgreSQL (project system database, default name: `finance_dashboard`)
- CORS: development origin `http://localhost:5173`

## Backend Service Surface

### Core endpoints
- `GET /health`
- `POST /parse`
- `GET /categories`
- `GET /categories/types`
- `POST /transactions/import`

### Rule lifecycle endpoints
- `GET /category-keywords`
- `POST /category-keywords`
- `PUT /category-keywords/{id}`
- `DELETE /category-keywords/{id}`
- `POST /category-keywords/validate-note`
- `GET /category-keywords/coverage`

### Admin (Phase 3 backend-first)
- `GET /admin/feature-flags`
- `PUT /admin/feature-flags/merchant-normalization`
- `GET /admin/classification-context`
- `POST /admin/classification-context/refresh` (always forces cache rebuild)
- `GET /admin/merchant-normalization-rules`
- `POST /admin/merchant-normalization-rules`
- `PUT /admin/merchant-normalization-rules/{id}`
- `DELETE /admin/merchant-normalization-rules/{id}`
- `POST /admin/merchant-normalization-rules/validate-note`
- `GET /admin/observability/summary`
- `GET /admin/observability/alerts`

## Classification Architecture

- Implementation module: `backend/category_classifier.py`
- Matcher utility: `backend/word_boundary_matcher.py`
- Observability utility: `backend/classification_observability.py`
- Endpoint integration: `backend/main.py`

### Classification pipeline
1. Keyword matching across global category context.
2. Category-name fallback across global category context.
3. Deterministic HTTP 400 guidance on unresolved notes.

### Deterministic resolution rules
- Lower `priority` wins.
- Lower `category_id` breaks equal-priority ties.

### Match strategies
- `substring`
- `word_boundary`
- `exact`

## Data Model

- `categories`: category metadata (`income`/`expense` type retained for reporting and filtering).
- `transactions`: imported transaction rows with required `category_id`.
- `category_keywords`: rule table with `match_type`, `is_active`, and audit columns.
- `transaction_classification_log`: optional observability table for classification outcomes.
- `classification_context_version`: cache-version table for immediate invalidation after rule writes.
- `merchant_normalization_rules`: global note-normalization rules (feature-flagged).

## Operational Notes

- `backend/database_setup.sql` is idempotent and safe to rerun.
- Backend environment is loaded from `backend/.env` via script-relative path.
- Rule loading uses in-memory cache keyed by DB version with immediate invalidation on rule changes.
- Database access uses a local `psycopg2` connection pool sized for current scale (`min=1`, `max=5` by default).
- Merchant normalization is optional and controlled by feature flag.
- Import observability tracks rolling one-hour thresholds for:
	- Classification failure rate alert: `> 10%` with minimum sample size `100`
	- Phase 3 fallback investigate signal: `> 20%` with minimum sample size `100`
	- Import latency warning: `POST /transactions/import` latency `> 1s`

## Architectural Trade-offs

### Pros
- Deterministic, explainable outcomes.
- Backend-owned rules reduce frontend complexity.
- Soft-delete rule lifecycle supports safe rollback.

### Constraints
- Rule-based matching can miss semantic aliases unless rules are maintained.
- `/admin/*` namespace is used for operational grouping and is currently unauthenticated by design.
- Cache and alerts are still process-local; multi-process deployments would need cross-process coordination.
