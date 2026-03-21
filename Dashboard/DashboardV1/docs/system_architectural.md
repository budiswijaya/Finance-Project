# System Architectural

## Overview

- Architecture style: single-page React frontend + FastAPI backend + PostgreSQL.
- Frontend responsibility: ingest files, normalize rows in grid UI, validate and submit payload.
- Backend responsibility: parse files, normalize dates, classify categories, persist transactions.
- Classification responsibility is backend-only to keep business rules centralized.

## Runtime Topology

- Frontend dev server: `http://localhost:5173`
- Backend API: `http://localhost:8003`
- Database: PostgreSQL (`finance_dashboard`)
- CORS is restricted to the Vite origin in development.

## Frontend Architecture

- App entry renders one main view (`NormalizedData`) with no route segmentation.
- UI is built around a dual-grid model:
  - Original Data grid (raw parsed rows)
  - Normalized Data grid (mapped and append-only rows)
- State model separates grid shape from row objects:
  - Grid state: rows/columns for ReactGrid rendering
  - Object state: normalized plain objects for API submission
- Undo/redo uses a ref-backed history hook to avoid excessive rerenders.

## Backend Architecture

- API endpoints:
  - `GET /health`
  - `POST /parse`
  - `GET /categories`
  - `GET /categories/types`
  - `POST /transactions/import`
- Parsing pipeline is format-specific (CSV, Excel, JSON, TXT) with unified output `List[Dict[str, Any]]`.
- Date normalization runs after parse and converts recognized formats to `YYYY-MM-DD`.
- Import flow builds in-memory lookup maps once per request, then classifies each row and inserts in a single transaction.

## Category Classification Architecture

- Classifier implementation is isolated in `backend/category_classifier.py`.
- Import endpoint in `backend/main.py` prepares typed maps and delegates classification.
- Three-phase strategy:
  1. Keyword match in transaction-type scope (`income` for positive amounts, `expense` for zero/negative)
  2. Category-name fallback in the same type scope
  3. HTTP 400 with type-scoped keyword/category guidance
- Tie-break behavior is deterministic:
  - lower priority number wins
  - lower category ID breaks equal-priority ties

## Data Model

- `categories`: canonical category entities with type (`income` or `expense`)
- `transactions`: persisted imported transactions with required `category_id`
- `category_keywords`: category rule metadata (`keyword`, `priority`) with FK cascade on delete
- Setup script keeps seed insertion idempotent and unique keyword/category pairs enforced.

## Operational Notes

- `backend/database_setup.sql` is rerunnable; unique constraint creation is guarded.
- Environment variables are loaded via `python-dotenv` from local env files.
- Versioned template is `backend/.env.example`; local `.env` files are ignored by git.

## Architectural Trade-offs

- Pros:
  - Simple operational model and easy local setup
  - Deterministic, explainable rule-based classification
  - Stateless per-request classification behavior
- Constraints:
  - Global psycopg2 connection is not pooled and not reconnect-safe
  - Substring keyword matching can produce false positives
  - No auth boundary beyond CORS in local/dev profile
