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
