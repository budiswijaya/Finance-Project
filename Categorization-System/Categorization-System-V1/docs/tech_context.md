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
| Server | Uvicorn 0.24.0 |
| Language | Python (version not pinned in requirements) |
| DB driver | `psycopg2` + local `SimpleConnectionPool` (PostgreSQL) |
| File parsing | `pandas` 2.1.4 + `openpyxl>=3.1.5` |
| Config | `python-dotenv 1.0.0` — reads `.env` for `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| Additional | `python-multipart` 0.0.6 (for multipart form handling), `httpx` 0.27.2 (HTTP client for testing) |
| Port | 8003 |

### CORS
- Allows only `http://localhost:5173` (Vite dev server)
- All methods and headers permitted for that origin

## Database

- PostgreSQL
- Schema defined in `backend/database_setup.sql`
- Phase 1/2 tables: `categories`, `transactions`, `category_keywords`, `transaction_classification_log`
- Phase 3 tables: `classification_context_version`, `merchant_normalization_rules`
- Sample categories seeded in SQL script
- Sample keyword rules are seeded with dynamic category name lookup (no hard-coded IDs)
- Keyword rules support mixed matching (`substring`, `word_boundary`, `exact`) with soft-delete (`is_active`)
- Classification outcomes can be logged to `transaction_classification_log` for observability and later analytics
- Classification logic is isolated in `backend/category_classifier.py` and called by `backend/main.py`

### Complete API Reference
All 32 endpoints are fully documented in [conventions.md](conventions.md#backend) with complete categorization by feature area and descriptions.

## Development Setup

### Backend Setup
1. Create `backend/.env` from `backend/.env.example`:
   ```
   DB_HOST=localhost
   DB_NAME=finance_dashboard
   DB_USER=postgres
   DB_PASSWORD=postgres
   ```
2. Initialize database: `python -m psycopg2 -U postgres < backend/database_setup.sql`
3. Install dependencies: `pip install -r backend/requirements.txt`
4. Start backend: `python backend/main.py` (or `run_backend.bat` on Windows)
   - Listens on `http://localhost:8003`
   - Database setup runs automatically on first startup

### Frontend Setup
1. Install dependencies: `npm install`
2. Start dev server: `npm run dev` (Vite on `http://localhost:5173`)
3. Build for deployment: `npm run build` (outputs to `dist/`)

### Full Stack Integration
- Frontend at `http://localhost:5173` ↔ Backend at `http://localhost:8003`
- Backend environment is loaded from `backend/.env` via script-relative path (not cwd-dependent)

## Known Constraints

- API has no auth boundary in current local/dev design
- ReactGrid column resize requires paid license
- In-memory cache and observability alerts are process-local (single-instance scope)
