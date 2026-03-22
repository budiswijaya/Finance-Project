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

#### Health & Information
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |

#### File Parsing
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/parse` | Parse uploaded file (CSV, XLSX, JSON, TXT); returns normalized rows |

#### Category Management (CRUD)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/categories` | List all categories with metadata |
| POST | `/categories` | Create new category |
| PUT | `/categories/{category_id}` | Update category name and type |
| DELETE | `/categories/{category_id}` | Delete category (requires `force=true` if category has transactions) |
| GET | `/categories/{category_id}/usage` | Get transaction count for category |
| GET | `/categories/types` | List distinct category types (income, expense) |

#### Category Keywords (Classification Rules)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/category-keywords` | List all classification rules |
| POST | `/category-keywords` | Create new keyword rule with priority and match type |
| PUT | `/category-keywords/{keyword_id}` | Update rule priority, keyword, or match type |
| DELETE | `/category-keywords/{keyword_id}` | Soft-delete rule (mark `is_active=false`) |
| POST | `/category-keywords/validate-note` | Test note against current rules (returns matched category) |
| GET | `/category-keywords/coverage` | Get coverage stats (how many transaction notes match rules) |

#### Transactions
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/transactions/import` | Bulk import transactions with auto-classification; supports optional `debug=true` query param |

#### Admin Feature Flags
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/feature-flags` | Get all feature flag states |
| PUT | `/admin/feature-flags/merchant-normalization` | Toggle merchant normalization feature |

#### Admin Classification Context
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/classification-context` | Get cached classification rules (keywords + categories) |
| POST | `/admin/classification-context/refresh` | Force rebuild cache and invalidate version |

#### Admin Merchant Normalization Rules
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/merchant-normalization-rules` | List all merchant normalization rules |
| POST | `/admin/merchant-normalization-rules` | Create new note-normalization rule (regex pattern) |
| PUT | `/admin/merchant-normalization-rules/{rule_id}` | Update normalization rule |
| DELETE | `/admin/merchant-normalization-rules/{rule_id}` | Soft-delete normalization rule |
| POST | `/admin/merchant-normalization-rules/validate-note` | Test note against normalization rules (returns normalized note) |

#### Admin Category Management Aliases
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/admin/categories` | Alias for `POST /categories` (operational namespace) |
| GET | `/admin/categories/{category_id}/usage` | Alias for `GET /categories/{category_id}/usage` |
| PUT | `/admin/categories/{category_id}` | Alias for `PUT /categories/{category_id}` |
| DELETE | `/admin/categories/{category_id}` | Alias for `DELETE /categories/{category_id}` |

#### Admin Observability
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/observability/summary` | Get import stats (latency, success rate, failure counts) |
| GET | `/admin/observability/alerts` | Get active alerts (classification failure > 10%, fallback > 20%, latency > 1s) |

### Error Handling
- All errors raised as `HTTPException` with descriptive `detail` strings
- Connection-level errors rollback transaction before re-raising
- Validation errors return HTTP 400; infrastructure errors return HTTP 500

### Date Normalization Convention
- All dates normalized to `YYYY-MM-DD` (date only, no time component)
- Detection is regex-based, parsing multi-format via ordered pattern list

### Soft-Delete Pattern
- `category_keywords` and `merchant_normalization_rules` use `is_active` boolean column instead of hard delete
- `DELETE` endpoints mark records as inactive, preserving audit trail
- Soft-deleted records are excluded from classification and rule loading
- Supports safe rollback by toggling `is_active` back to `true`
