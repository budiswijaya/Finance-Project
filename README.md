# Project Description: Finance Data Normalization and Categorization System

**Short Name:** Finance Categorization System

**Author:** Architecture Team  
**Date:** March 22, 2026  
**Status:** Active  
**Version:** 1.0

---

## 1. Problem Statement

This project helps users import finance data from files, clean and normalize that data, and save transactions into a database with automatic category assignment.

Before this system, users had to classify many transactions manually. That was slow, error-prone, and hard to maintain. The goal of this project is to make the workflow understandable, repeatable, and easy to improve.

Why this matters:
- Faster transaction processing
- More consistent category assignment
- Better visibility into why a category was chosen

---

## 2. Goals

- Build a full import pipeline from file upload to database insert
- Provide deterministic category classification (same input gives same output)
- Support rule-based category management for admins
- Give beginner developers a clear architecture and operational model

---

## 3. Non-Goals

- Machine learning classification
- Multi-tenant account isolation
- Advanced authentication/authorization design
- Distributed cache or microservices deployment

---

## 4. Architecture Overview

The system is a single frontend + single backend + PostgreSQL architecture.

High-level runtime:

```text
┌────────────────────────────────────────────────────────────────────┐
│        Finance Data Normalization and Categorization System        │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Frontend (React + Vite)                                           │
│  • File upload                                                      │
│  • Data normalization grid                                          │
│  • Category admin panel                                             │
│         │                                                           │
│         ▼ HTTP (REST)                                               │
│  Backend (FastAPI)                                                  │
│  • Parser endpoints (/parse)                                        │
│  • Import pipeline (/transactions/import)                           │
│  • Category engine + keyword rules                                  │
│  • Admin APIs (/admin/*)                                            │
│         │                                                           │
│         ▼ SQL                                                       │
│  PostgreSQL                                                         │
│  • categories                                                       │
│  • category_keywords                                                │
│  • transactions                                                     │
│  • transaction_classification_log                                   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 5. Components

### 5.1 Frontend App Shell
- **Location:** `src/App.tsx`
- **Responsibility:** Mounts the main workflow component.
- **Key point for juniors:** This file is intentionally small. Most behavior lives in the feature component.

### 5.2 Frontend Main Workflow
- **Location:** `src/NormalizedData.tsx`
- **Responsibility:**
  - Upload and parse file
  - Map source fields into target columns (`Date`, `Note`, `Amount`)
  - Edit rows in grid
  - Validate, calculate totals, submit transactions
  - Manage categories in admin panel
- **Key UI patterns:**
  - React state + hooks (`useState`, `useMemo`, `useCallback`)
  - ReactGrid for table editing
  - API helper functions for backend calls and fallback behavior

### 5.3 Backend API Layer
- **Location:** `backend/main.py`
- **Responsibility:** Exposes all REST endpoints used by frontend and admin operations.

### 5.4 Backend Parser Engine
- **Location:** `backend/main.py` parser functions
- **Responsibility:** Converts uploaded file content into structured rows.
- **Supported formats:** CSV, Excel, JSON, text-delimited.
- **Important detail:** Date normalization tries many date formats to produce consistent `YYYY-MM-DD` output.

### 5.5 Backend Category Engine
- **Location:** `backend/main.py` classification functions
- **Responsibility:** Determine `category_id` for each transaction note using a 3-phase deterministic strategy.
- **Phases:**
  - Phase 1: Keyword match (priority first, then category id tie-break)
  - Phase 2: Category-name fallback match
  - Phase 3: Error with guidance when no match found

### 5.6 Backend Context Cache
- **Location:** `backend/main.py` cache helpers
- **Responsibility:** Cache category/keyword context in memory and refresh by version.
- **Reason:** Avoid repeated heavy DB reads on every transaction row.

### 5.7 Backend Admin and Observability
- **Location:** `backend/main.py` `/admin/*` endpoints
- **Responsibility:**
  - Feature flags (merchant normalization on/off)
  - Cache status and forced refresh
  - Merchant normalization rule CRUD
  - Import observability summary and alerts

### 5.8 Database Layer
- **Location:** PostgreSQL + `backend/database_setup.sql`
- **Responsibility:** Persist all categories, rules, transactions, and optional logs.

---

## 6. Data Flow

### 6.1 Parse and Normalize Flow

```text
User uploads file
    │
    ▼
POST /parse
    │
    ▼
Backend parser returns rows
    │
    ▼
Frontend grid editing + column mapping
    │
    ▼
Normalized rows ready for submit
```

### 6.2 Import and Category Assignment Flow

```text
POST /transactions/import (rows[])
    │
    ├─ Validate date/amount per row
    ├─ (Optional) normalize merchant note via feature flag
    ├─ Determine category_id via 3-phase classifier
    ├─ Insert into transactions
    └─ (Optional) write classification log
    │
    ▼
Return inserted count (+ debug metadata if requested)
```

### 6.3 Category Rule Management Flow

```text
Admin UI
  ├─ GET /categories
  ├─ POST /categories
  ├─ PUT /categories/{id}
  └─ DELETE /categories/{id}

Keyword APIs
  ├─ GET /category-keywords
  ├─ POST /category-keywords
  ├─ PUT /category-keywords/{id}
  └─ DELETE /category-keywords/{id} (soft delete)
```

### 6.4 Beginner Walkthrough: One Transaction End-to-End

Use this as a mental model when reading the code:

1. User uploads a CSV/Excel/JSON/text file in frontend.
2. Frontend sends file to `POST /parse`.
3. Backend parser converts file into row objects.
4. Frontend shows rows in editable grid (`src/NormalizedData.tsx`).
5. User maps source columns into target fields: Date, Note, Amount.
6. User reviews/edits rows and clicks submit.
7. Frontend sends normalized rows to `POST /transactions/import`.
8. Backend loads classification context (categories + active rules) from cache or DB.
9. For each row, backend validates date and amount.
10. Backend optionally normalizes merchant note if feature flag is enabled.
11. Backend runs classification engine:
    - Phase 1 keyword match
    - Phase 2 category-name fallback
    - Phase 3 error if still unmatched
12. Backend inserts successful rows into `transactions` table.
13. Backend optionally writes classification details to observability log table.
14. Backend returns insert count (and debug metadata if requested).
15. Frontend shows success/failure message to the user.

This flow is the heart of the system. If you understand this, you understand the project.

---

## 7. Technology Choices

| Technology | Purpose | Rationale |
|---|---|---|
| React + TypeScript | Frontend UI | Strong developer ergonomics and safer refactoring |
| Vite | Frontend dev/build tool | Fast local development and simple setup |
| FastAPI | Backend API framework | Clear endpoint model and strong Python ecosystem |
| psycopg2 + connection pool | PostgreSQL access | Reliable SQL control with pooled connections |
| PostgreSQL | Data store | Strong relational model and indexing support |
| ReactGrid | Editable tabular UI | Good fit for spreadsheet-like normalization tasks |

---

## 8. Integration Points

- Frontend to backend over HTTP (`http://localhost:5173` -> `http://localhost:8003`)
- Backend to PostgreSQL using DB credentials from `backend/.env`
- File parsing pipeline accepts user-uploaded data and transforms it to internal row format

---

## 9. Security Considerations

- SQL uses parameterized queries (`%s`) to reduce injection risk
- Input validation checks key payload fields (date, amount, match types)
- Soft delete strategy preserves auditability of rule lifecycle
- Current setup is local/dev oriented and does not include full auth boundaries

---

## 10. Scalability and Performance

Current model:
- Single backend service process
- Local in-memory cache for classification context
- Connection pool in backend process
- In-memory observability windows for import metrics

Known limits:
- No distributed cache
- No multi-instance synchronization
- Large batch imports are memory-bound

---

## 11. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Bad input file format | Parse/import failure | Clear parse errors and editable grid before submit |
| Missing keyword coverage | Phase 3 classification errors | Rule validation endpoint and admin CRUD for keywords |
| Stale cache after rule changes | Incorrect classification | Versioned context + explicit cache invalidation |
| Duplicate active keyword rules | Conflict and ambiguity | Partial unique index on active rows only |
| Slow import endpoint | Poor UX | Latency warnings + observability endpoints |

---

## 12. Deployment Architecture

Environments:
- Development: local frontend + local backend + local PostgreSQL
- Production: same pattern with production hosts and secured config

Deployment diagram:

```text
┌──────────────────────────────────────────────────────────────┐
│                        Environment                            │
├──────────────────────────────────────────────────────────────┤
│  Browser                                                      │
│    │                                                          │
│    ▼                                                          │
│  Frontend (React/Vite)                                        │
│    │ HTTP                                                     │
│    ▼                                                          │
│  Backend (FastAPI)                                            │
│    │ SQL                                                      │
│    ▼                                                          │
│  PostgreSQL                                                   │
└──────────────────────────────────────────────────────────────┘
```

Basic startup:
1. Start backend (`python backend/main.py`)
2. Start frontend (`npm run dev`)
3. Ensure DB schema exists (`backend/database_setup.sql`)

---

## 13. Observability

- **Logs:** API exceptions and optional classification logs
- **Metrics:** import latency, failure rate, phase 3 fallback rate
- **Alerts:** rolling-window warnings available via admin endpoints

Admin observability endpoints:
- `GET /admin/observability/summary`
- `GET /admin/observability/alerts`

---

## 14. Open Questions

- Should we add authentication and role-based access for admin endpoints?
- Should large imports move to async/background jobs?
- Should cache and observability move to shared infrastructure for multi-instance deployment?
- Should we split `src/NormalizedData.tsx` into smaller feature modules for easier onboarding?

---

## 15. References

- `README.md`
- `backend/main.py`
- `backend/database_setup.sql`
- `docs/testing.md`
- `docs/system_patterns.md`

---

## 16. Beginner Glossary

- **Parser:** Code that reads a file and turns it into structured rows.
- **Normalization:** Making data consistent (same columns, same date format, clean amount values).
- **Classification engine:** Logic that decides which category a transaction belongs to.
- **Soft delete:** Mark a row as inactive instead of physically removing it.
- **Observability:** Logs/metrics/alerts that help us understand system behavior.
- **Cache:** Temporary in-memory data used to speed up repeated operations.
