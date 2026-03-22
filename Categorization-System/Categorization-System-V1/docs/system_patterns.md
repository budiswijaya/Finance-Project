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
- `determine_category_id()` uses a three-phase strategy:
  1. **Keyword matching (primary)**: Loads all active `category_keywords` rules across both types; matches keywords in transaction note with deterministic priority ordering (lower priority number wins; category ID breaks ties)
  2. **Category name matching (fallback)**: Falls back to substring matching of category names across both types for backward compatibility
  3. **Error with guidance (final)**: Lists all available keywords and category names user can use
- If no match found, raises HTTP 400 asking user to include a keyword or category name in the note
- Amount sign does not control classification scope; positive and negative amounts use the same global rule set
- Import endpoint supports optional debug mode (`POST /transactions/import?debug=true`) that returns classification metadata while default response remains unchanged

### Keyword Matching Strategy
- **Data loading**: Classification context uses an in-memory cache keyed by `classification_context_version`; cache is rebuilt from DB snapshot when version changes or refresh is forced
- **Deterministic tie-breaking**: If note contains multiple keywords:
  - Primary: Keyword with lower priority number wins (priority 1 > priority 2)
  - Secondary: If same priority across categories, lower category ID wins
  - Example: note="cafe grab lunch" with {cafe→Food p:1, grab→Transport p:2} → Food & Dining (priority 1 wins)
- **Matching rules**: Mixed rule types are supported per keyword (`substring`, `word_boundary`, `exact`)
- **Soft-delete rules**: Inactive rules (`is_active=false`) are excluded from runtime classification
- **Seed data**: Uses dynamic category lookup by name instead of hard-coded IDs (stable across schema changes)
- **Uniqueness**: partial unique index `idx_active_keywords` ensures no duplicate active keyword/category pairs while allowing soft-delete reactivation

### Phase 3 Backend Runtime Patterns
- **Immediate cache invalidation**: keyword-rule and merchant-normalization writes bump `classification_context_version` and clear in-memory cache immediately after successful commit
- **Forced cache rebuild endpoint**: `POST /admin/classification-context/refresh` always rebuilds cache and ignores version mismatch
- **Local connection pooling**: backend requests acquire pooled `psycopg2` connections (`min=1`, `max=5` default) instead of sharing a single global connection
- **Feature-flagged note normalization**: merchant normalization is global and only applied when `merchant_normalization_enabled=true`
- **Word-boundary normalization**: `word_boundary` merchant-normalization rules use true `\b...\b` boundaries (not escaped literals), so token cleanup is applied as configured
- **Diagnostics parity**: `/category-keywords/validate-note` and import path both use the same normalization + classification flow to avoid behavior drift
- **Admin namespace**: Phase 3 operational endpoints live under `/admin/*` for operational grouping

### Import Observability Thresholds (Simple Rules)
- Scope: only `POST /transactions/import`
- Window: rolling `1 hour`
- Minimum sample size: `100`
- Alert: classification failure rate `> 10%`
- Investigate: Phase 3 fallback rate `> 20%`
- Warning: import latency `> 1 second`

### Rule Management API
- Keyword lifecycle is managed via backend endpoints:
  - `GET /category-keywords`
  - `POST /category-keywords`
  - `PUT /category-keywords/{keyword_id}`
  - `DELETE /category-keywords/{keyword_id}` (soft delete)
  - `POST /category-keywords/validate-note`
  - `GET /category-keywords/coverage`
- `/category-keywords/validate-note` reuses production classifier logic to avoid drift between diagnostics and import behavior

### Operations API Pattern
- `/admin/feature-flags` and `/admin/feature-flags/merchant-normalization` control runtime toggles
- `/admin/classification-context` and `/admin/classification-context/refresh` expose cache status and force refresh
- `/admin/merchant-normalization-rules*` manages global merchant normalization rules
- `/admin/observability/*` exposes rolling threshold summary and recent warning/alert events
- Category mutation routes (`POST /categories`, `PUT|DELETE /categories/{id}`) are open in current local/dev design

### Admin UI Pattern
- Admin workflow is embedded into the existing `NormalizedData` control panel instead of adding routing or a separate admin app
- UI covers feature flag control, forced cache rebuild, observability summary, merchant normalization rule management, category keyword management, and note validation workflows

### Classification Observability
- Classification outcomes are persisted to `transaction_classification_log` when the table exists
- Log rows include phase, resolution path, matched keyword, and hashed note to support later analytics and rule tuning

### Database
- Four tables: `categories (id, name, icon, type, created_at)`, `transactions (id, date, amount, note, category_id, created_at)`, `category_keywords (id, category_id, keyword, priority, match_type, is_active, created_at, updated_at, created_by)`, and `transaction_classification_log`
- `category_id` is a required FK — every transaction must have a category
- `category_keywords.category_id` cascades on delete, so keyword rules are treated as dependent metadata for a category
- `category_keywords` is queried at runtime during transaction import with LEFT JOIN to support categories with no keywords
- `category_keywords` has partial unique index `idx_active_keywords ON (category_id, keyword) WHERE is_active=TRUE` to prevent duplicate active rules while enabling soft-delete reactivation
- Local `psycopg2` connection pool is used for backend request isolation at current scale

## Save / Load
- Saves `{normalizedGridRows, normalizedRows, normalizedGridCols, timestamp}` to `localStorage` under key `"normalizedDataState"`
- Load restores all three states; alerts with save timestamp
- No versioning — format mismatch silently fails validation check

## Soft-Delete Pattern

Both `category_keywords` and `merchant_normalization_rules` use soft-delete semantics:

### Data Model
- `is_active` boolean column (default `true` on insert)
- Deleted records are marked `is_active = false` instead of physically deleted
- Enables audit trail and safe rollback

### DELETE Endpoint Behavior
- `DELETE /category-keywords/{keyword_id}` → marks record `is_active = false`
- `DELETE /admin/merchant-normalization-rules/{rule_id}` → marks record `is_active = false`
- Both return HTTP 204 (success with no content)
- Reactivation is possible by toggling `is_active` back to `true` via PUT endpoint

### Runtime Classification
- Inactive rules (`is_active = false`) are excluded from `determine_category_id()` and note normalization flows
- Keyword rules use partial unique index `idx_active_keywords` to prevent duplicate active rules while allowing reactivation
- Observability and rule management endpoints filter to exclude inactive records by default

### Rollback & Migration Safety
- Soft-delete enables safe rollback if a rule deployment causes issues
- Historical classification outcomes (if logged) reference soft-deleted rules for audit trail
- Safe to re-insert the same keyword/rule by toggling `is_active = true`
