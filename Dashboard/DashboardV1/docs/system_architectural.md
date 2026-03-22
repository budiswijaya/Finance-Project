# System Architectural

## Overview

- Architecture style: React SPA frontend + FastAPI backend + PostgreSQL.
- Frontend responsibility: parse preview, normalize data, and submit transaction rows.
- Backend responsibility: classification, validation, persistence, and rule lifecycle APIs.
- Classification logic is centralized in backend for deterministic behavior.

## Runtime Topology

- Frontend dev server: `http://localhost:5173`
- Backend API: `http://localhost:8003`
- Database: PostgreSQL (`finance_dashboard`)
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

## Operational Notes

- `backend/database_setup.sql` is idempotent and safe to rerun.
- Backend environment is loaded from `backend/.env` via script-relative path.
- Rule loading is per-request snapshot based for deterministic behavior.

## Architectural Trade-offs

### Pros
- Deterministic, explainable outcomes.
- Backend-owned rules reduce frontend complexity.
- Soft-delete rule lifecycle supports safe rollback.

### Constraints
- Global psycopg2 connection is not pooled.
- Rule-based matching can miss semantic aliases unless rules are maintained.
- No auth boundary beyond local/dev CORS assumptions.
