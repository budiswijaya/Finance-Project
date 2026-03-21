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
