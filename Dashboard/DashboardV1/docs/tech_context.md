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
