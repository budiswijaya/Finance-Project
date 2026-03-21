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
