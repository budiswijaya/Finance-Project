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
- `determine_category_id()` does keyword matching: checks if any category name appears as a substring of the transaction note
- If no match found, raises HTTP 400 asking user to include a category keyword in the note

### Database
- Two tables: `categories (id, name, icon, type, created_at)` and `transactions (id, date, amount, note, category_id, created_at)`
- `category_id` is a required FK — every transaction must have a category
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
| File parsing | `pandas` 2.1.4 + `openpyxl` 3.1.2 |
| Config | `python-dotenv` — reads `.env` for `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| Port | 8003 |

### CORS
- Allows only `http://localhost:5173` (Vite dev server)
- All methods and headers permitted for that origin

## Database

- PostgreSQL
- Schema defined in `backend/database_setup.sql`
- Two tables: `categories`, `transactions`
- Sample categories seeded in SQL script

## Development Setup

1. Start backend: `python backend/main.py` (or `run_backend.bat`)
2. Start frontend: `npm run dev` (Vite on port 5173)
3. Frontend calls backend at `http://localhost:8003`

## Known Constraints

- Global psycopg2 connection — not reconnect-safe, not connection-pooled
- No auth — API is open, CORS is the only boundary
- ReactGrid column resize requires paid license

# Testing

## Current State

No automated tests are present in this project. There is no test runner configured in `package.json` and no test files in `src/`.

## Manual Testing Approach

The current workflow relies on manual browser testing:
1. Upload a file and verify the original grid renders correctly
2. Map columns and click **Add Data** — verify rows append to normalized grid
3. Edit cells in either grid and verify undo (Ctrl+Z) / redo (Ctrl+Y / Ctrl+Shift+Z) works
4. Use Delete Row / Delete Column buttons after focusing a cell
5. Click **Calculate** and verify summary message
6. Click **Submit** and check backend response
7. **Save** to localStorage and **Load** to verify persistence

## Backend Endpoints (Manual)

- `GET http://localhost:8003/health` — verify server is running
- `POST http://localhost:8003/parse` — test file parsing with multipart form
- `GET http://localhost:8003/categories/types` — verify category types exist before import
- `POST http://localhost:8003/transactions/import` — test bulk import

## Key Things to Test When Modifying

- **Undo/redo**: Changes to grid state must push to `useHistory`
- **Append logic**: Multiple file uploads should accumulate rows, not reset
- **Category matching**: Transaction notes must contain category keywords for auto-assignment
- **Amount parsing**: Parentheses `(200.00)` → `-200`, currency symbols stripped, negatives preserved
- **Date normalization**: Various date formats all resolve to `YYYY-MM-DD`
