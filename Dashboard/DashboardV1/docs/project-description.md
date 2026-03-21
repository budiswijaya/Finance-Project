# Conventions

## Frontend

### File Structure
```
src/
  App.tsx           — root component, renders <NormalizedData />
  NormalizedData.tsx — single monolithic component (all logic + UI)
  App.css
  index.css
  main.tsx
```

### Naming
- React component: `PascalCase` exports (`export function NormalizedData`)
- Event handlers: `handle` prefix (`handleNormalize`, `handleFileChange`, `handleSubmit`)
- Delete handlers: `deleteSelected{Grid}{RowOrColumn}` pattern
- Grid state pairs: `{original|normalized}Grid{Rows|Cols}` for ReactGrid state; `normalizedRows` for plain object array
- Focus state: `{original|normalized}Focus`

### State Organization
- All state at top of component, grouped before effects
- `useMemo` for derived values (`originalHeaders`, `normalizedSummary`)
- `useCallback` for all event handlers
- History tracking via `useHistory` custom hook (ref-based)

### Row / Cell IDs
- Header row: `rowId = "header"`
- Data rows (original): `rowId = "nrow-{idx}"` (0-indexed from load)
- Data rows (normalized): `rowId = "nrow-{currentRowCount + idx}"` (globally sequential for appending)
- Row index column: `columnId = "rowIndex"` — always first column, never included in data

### Normalized Object Keys
- Always lowercase: `{ date, note, amount }`
- `amount` is stored as a number (parsed via `parseAmount`)
- `date` and `note` are strings

## Backend

### API Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/parse` | Parse uploaded file |
| GET | `/categories` | List all categories |
| GET | `/categories/types` | List distinct category types |
| POST | `/transactions/import` | Bulk import transactions |

### Error Handling
- All errors raised as `HTTPException` with descriptive `detail` strings
- Connection-level errors rollback transaction before re-raising
- Validation errors return HTTP 400; infrastructure errors return HTTP 500

### Date Normalization Convention
- All dates normalized to `YYYY-MM-DD` (date only, no time component)
- Detection is regex-based, parsing multi-format via ordered pattern list

# Formatting

## Frontend (TypeScript / TSX)

- **Language**: TypeScript ~5.8, strict mode (inferred — no explicit `strict` in tsconfig observed but types are consistently annotated)
- **Module system**: ESM (`"type": "module"` in package.json)
- **Indentation**: 2 spaces
- **Quotes**: Double quotes for JSX strings and imports
- **Semicolons**: Yes
- **Arrow functions**: Preferred for callbacks and inline functions
- **Type assertions**: Avoided — typed interfaces used instead (`ParsedData`, `HistoryState`, `SavedState`)
- **`any` usage**: Present in several places (grid cell access, row objects) — accepted as pragmatic given dynamic data shapes
- **Linter**: ESLint 9 with `eslint-plugin-react-hooks` (enforces hook rules) and `eslint-plugin-react-refresh`

## Backend (Python)

- **Indentation**: 4 spaces
- **String quotes**: Double quotes for docstrings, single or double for inline strings
- **Type hints**: Used on all function signatures
- **Docstrings**: Present on all endpoint and utility functions
- **Import order**: stdlib → third-party → local (standard Python convention)

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

# System Patterns

## High-Level Architecture

- **Single-page app** — no routing; one view rendered through `App.tsx` → `NormalizedData`
- **Dual-grid layout** — Original Data grid (left) and Normalized Data grid (right) displayed side-by-side
- **Append-only normalization** — new file uploads append to existing normalized rows instead of replacing them, allowing multi-source data aggregation
- **Calculate → Submit gate** — user must press Calculate (validates data) before Submit is enabled; `isCalculated` flag enforces this

## Data Flow

```
File Upload
  → POST /parse (FastAPI)
  → ParsedData { filename, fileType, rows[] }
  → Original grid (ReactGrid)
  → User maps columns via dropdowns (mapping state)
  → handleNormalize → appends to Normalized grid
  → User edits cells directly in either grid
  → handleCalculate (validate + summarize)
  → handleSubmit → POST /transactions/import
```

## Key Frontend Patterns

### `useHistory` Custom Hook
- Ref-based (not state-based) undo/redo — avoids re-render loops
- Snapshots full `HistoryState` (`originalGridRows`, `normalizedGridRows`, `normalizedRows`, `normalizedGridCols`) via `JSON.parse(JSON.stringify(...))`
- Max 100 states (`MAX_HISTORY_SIZE`); oldest dropped when exceeded
- `isProcessingRef` prevents recursive pushes during undo/redo
- **Limitation**: `canUndo`/`canRedo` are computed from refs at render time — they don't trigger re-renders on their own

### Grid ↔ Object Conversion
- `buildGridRows(dataRows, columns)` — converts plain objects to ReactGrid `Row[]`
- `rowsToObjects(rows, cols)` — converts `Row[]` back to plain objects; calls `parseAmount` for Amount column
- `rowIndex` is a virtual display-only column, always excluded from data conversion (`columnId !== 'rowIndex'`)

### Focus-Based Delete
- `originalFocus` / `normalizedFocus` track the last focused cell (`{rowId, columnId}`)
- Delete Row: filters out the focused `rowId` from grid rows
- Delete Column: filters out the focused `columnId` from columns and removes that cell index from every row
- Focus advances to next available row/column after deletion

### Column Mapping
- `mapping` state: `Record<sourceColumnId, targetField>` where target ∈ `["Date", "Note", "Amount", "Ignore"]`
- `TARGET_COLUMNS = ["Date", "Note", "Amount"]` defines the fixed normalized schema
- `Ignore` is a valid selection that excludes the column from normalization

## Key Backend Patterns

### File Parsing Pipeline
- Single `/parse` endpoint accepts CSV, Excel (.xlsx/.xls), JSON, TXT
- Each format has a dedicated parser function; output is always `List[Dict[str, Any]]`
- `parse_date()` runs on all parsed rows — detects date-like strings via regex and normalizes to `YYYY-MM-DD`

### Category Auto-Assignment
- `/transactions/import` refuses submissions unless both `income` and `expense` category types exist in DB
- `determine_category_id()` uses a three-phase strategy:
  1. **Keyword matching (primary)**: Loads all `category_keywords` rules filtered by transaction type; matches keywords in transaction note with deterministic priority ordering (lower priority number wins; category ID breaks ties)
  2. **Category name matching (fallback)**: Falls back to substring matching of category names for backward compatibility
  3. **Error with guidance (final)**: Lists all available keywords and category names user can use
- If no match found, raises HTTP 400 asking user to include a keyword or category name in the note
- Transaction type (income/expense) is inferred from amount sign; only keywords for that type are considered

### Keyword Matching Strategy
- **Data loading**: At request time, keywords are loaded once per import with a LEFT JOIN between categories and category_keywords
- **Deterministic tie-breaking**: If note contains multiple keywords:
  - Primary: Keyword with lower priority number wins (priority 1 > priority 2)
  - Secondary: If same priority across categories, lower category ID wins
  - Example: note="cafe grab lunch" with {cafe→Food p:1, grab→Transport p:2} → Food & Dining (priority 1 wins)
- **Matching rules**: Substring matching (`keyword in note_lower`); no word boundaries yet (Phase 2 enhancement)
- **Seed data**: Uses dynamic category lookup by name instead of hard-coded IDs (stable across schema changes)
- **Uniqueness**: `UNIQUE(category_id, keyword)` constraint prevents duplicate keyword/category pairs

### Database
- Three tables: `categories (id, name, icon, type, created_at)`, `transactions (id, date, amount, note, category_id, created_at)`, and `category_keywords (id, category_id, keyword, priority, created_at)`
- `category_id` is a required FK — every transaction must have a category
- `category_keywords.category_id` cascades on delete, so keyword rules are treated as dependent metadata for a category
- `category_keywords` is queried at runtime during transaction import with LEFT JOIN to support categories with no keywords
- `category_keywords` has UNIQUE constraint on `(category_id, keyword)` to prevent duplicate rules
- Global `psycopg2` connection (not pooled, not per-request)

## Save / Load
- Saves `{normalizedGridRows, normalizedRows, normalizedGridCols, timestamp}` to `localStorage` under key `"normalizedDataState"`
- Load restores all three states; alerts with save timestamp
- No versioning — format mismatch silently fails validation check

# Tech Context

## Frontend

| Item | Detail |
|------|--------|
| Framework | React 19 |
| Language | TypeScript ~5.8 |
| Build tool | Vite 7 (plugin: `@vitejs/plugin-react-swc`) |
| Grid library | `@silevis/reactgrid` v4.1.17 (free tier) |
| Linting | ESLint 9 + `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh` |
| Deploy | GitHub Pages via `gh-pages`; base path `/Project-Data-Normalization-Final/` |

### ReactGrid Notes
- Free tier is used — **column resize events are not available** (noted in code comment on `handleColumnsChanged`)
- `stickyTopRows={1}` and `stickyLeftColumns={1}` keep header and row-index pinned
- `enableRowSelection` and `enableColumnSelection` enable focus tracking used for delete operations

## Backend

| Item | Detail |
|------|--------|
| Framework | FastAPI 0.104.1 |
| Server | Uvicorn 0.24 |
| Language | Python (version not pinned in requirements) |
| DB driver | `psycopg2` (PostgreSQL) |
| File parsing | `pandas` 2.1.4 + `openpyxl>=3.1.5` |
| Config | `python-dotenv` — reads `.env` for `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| Port | 8003 |

### CORS
- Allows only `http://localhost:5173` (Vite dev server)
- All methods and headers permitted for that origin

## Database

- PostgreSQL
- Schema defined in `backend/database_setup.sql`
- Three tables: `categories`, `transactions`, `category_keywords`
- Sample categories seeded in SQL script
- Sample keyword rules are seeded with dynamic category name lookup (no hard-coded IDs)
- Keyword rules are queried and used during transaction import for classification (Phase 1)
- Classification logic is isolated in `backend/category_classifier.py` and called by `backend/main.py`

## Development Setup

1. Start backend: `python backend/main.py` (or `run_backend.bat`)
2. Start frontend: `npm run dev` (Vite on port 5173)
3. Frontend calls backend at `http://localhost:8003`
4. Local env template: `backend/.env.example` (copy to `backend/.env` for local use)

## Known Constraints

- Global psycopg2 connection — not reconnect-safe, not connection-pooled
- No auth — API is open, CORS is the only boundary
- ReactGrid column resize requires paid license

# Testing

## Current State

- Frontend: manual testing workflow, no frontend test runner configured in `package.json`.
- Backend category-classification: automated unit tests are present.

## Backend Automated Tests

- Test file: `test_category_keywords.py`
- Scope: imports production classifier (`backend/category_classifier.py`) and validates runtime behavior.
- Current suite size: 5 unit tests.

### Covered Behaviors

1. Keyword priority resolution
2. Deterministic tie-break by category ID
3. Category-name fallback remains type-scoped
4. Income-only keywords do not classify expense rows
5. Error guidance is type-scoped

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

## Regression Focus Areas

- Type-safe category assignment (`income` vs `expense`)
- Keyword priority and deterministic tie-break behavior
- Category-name fallback after keyword miss
- Date normalization to `YYYY-MM-DD`
- Amount parsing edge cases (currency symbols, negatives, parentheses)
