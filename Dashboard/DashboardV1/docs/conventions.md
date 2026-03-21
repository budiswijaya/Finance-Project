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
