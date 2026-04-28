<img
   src="https://raw.githubusercontent.com/budiswijaya/Finance-Project/blob/main/0.png"
   alt="Finance Data Normalization and Categorization System Setup"
/>
<img
   src="https://raw.githubusercontent.com/budiswijaya/Finance-Project/blob/main/1.png"
   alt="Finance Data Normalization and Categorization System Setup "
/>

# Project Description: Finance Data Normalization and Categorization System

**Short Name:** Finance Categorization System

**Author:** Budi S Wijaya  
**Date:** March 22, 2026 (Last Updated: April 28, 2026)  
**Status:** Active  
**Version:** 1.0 (Phase 3 Complete)

---

## 🚀 What this project does

This project is a backend-driven system that processes raw financial transactions and automatically categorizes them using deterministic rules. It’s designed to simulate how real-world finance systems handle messy, inconsistent transaction data—and how support engineers debug issues when classification goes wrong.

- Upload transaction files (CSV, Excel, JSON, text)
- Parse and normalize into structured data
- Automatically categorize transactions
- Store results in PostgreSQL
- Admin tools for managing rules and observability
  - categories
  - keyword rules
  - merchant normalization rules
  - observability / debugging data

## ⚙️ How it works (high-level flow)

```
Upload → Parse → Normalize → Classify → Store → Observe
```

1. File is uploaded via frontend
2. Backend parses it into structured rows
3. User confirms/edit mapping
4. Backend:
   - optionally normalizes merchant text
   - classifies using keyword rules
   - stores transactions
   - logs classification results

## 🔍 Classification Logic

The backend classifies each transaction in 3 steps:

1. Phase 1 → Basic Classification (Foundation)

```
"coffee" → Food & Dining
```

1. Phase 2 → Improved Matching + Observability

```
"Spent on food & dining" → Food & Dining
```

1. Phase 3 → Normalization + Feature Flags (Real-world handling)

```
"MCDONALDS #123" → Food & Dining
"GRABFOOD MCDONALDS" → Food & Dining
```

It demonstrates:

- handling messy real-world data
- building rule-based systems
- debugging production-like incidents
- understanding system behavior vs user expectations

## 🧪 Quick Examples

✅ Clean Case (works as expected)

```
"coffee shop" → Food & Dining
```

Reason:

- Clean input + direct keyword match = deterministic success

❌ Failure Case (real incident)

```
"MCDONALDS #123" → ❌ fails (before normalization)  → ✅ Should be Food & Dining
```

Reason:

- missing domain rule (no "mcdonalds" keyword)
- lack of preprocessing (noise not removed)
- System cannot classify → throws error

⚠️ Ambiguous Case (advanced, high-value)

```
"GRABFOOD MCDONALDS" → ❌ Transportation (unexpected) → ✅ Should be Food & Dining
```

Reason:

- Matches "grab" (Transportation)
- Also contains "mcdonalds" (Food)
- System picks based on rules, not meaning

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

## 3.5 System Evolution

The system has evolved through three phases:

- **Phase 1 (Core)**: Basic parsing, classification, and keyword rules
- **Phase 2 (Enhanced)**: Extended keyword matching, soft deletes, observability logging
- **Phase 3 (Production-Ready)**: Merchant normalization preprocessing, feature flags, admin operations, and observability alerts

Phase 3 was added in April 2026 to handle real-world transaction data issues and provide operational visibility.

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
│  • File upload                                                     │
│  • Data normalization grid                                         │
│  • Category admin panel                                            │
│         │                                                          │
│         ▼ HTTP (REST)                                              │
│  Backend (FastAPI)                                                 │
│  • Parser endpoints (/parse)                                       │
│  • Import pipeline (/transactions/import)                          │
│  • Category engine + keyword rules                                 │
│  • Admin APIs (/admin/*)                                           │
│         │                                                          │
│         ▼ SQL                                                      │
│  PostgreSQL                                                        │
│  • categories → list of categories                                 │
│  • category_keywords → rules for classification                    │
│  • transactions → stored results                                   │
│  • transaction_classification_log → debugging & observability      │
│  • merchant_normalization_rules (Phase 3) → clean noisy text       │
│  • classification_context_version (Phase 3) → cache invalidation   │
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
    ├─ (Optional) normalize merchant note via feature flag (Phase 3)
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
10. Backend optionally normalizes merchant note if feature flag is enabled (Phase 3).
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

| Technology                 | Purpose                 | Rationale                                         |
| -------------------------- | ----------------------- | ------------------------------------------------- |
| React + TypeScript         | Frontend UI             | Strong developer ergonomics and safer refactoring |
| Vite                       | Frontend dev/build tool | Fast local development and simple setup           |
| FastAPI                    | Backend API framework   | Clear endpoint model and strong Python ecosystem  |
| psycopg2 + connection pool | PostgreSQL access       | Reliable SQL control with pooled connections      |
| PostgreSQL                 | Data store              | Strong relational model and indexing support      |
| ReactGrid                  | Editable tabular UI     | Good fit for spreadsheet-like normalization tasks |

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

| Risk                           | Impact                        | Mitigation                                                |
| ------------------------------ | ----------------------------- | --------------------------------------------------------- |
| Bad input file format          | Parse/import failure          | Clear parse errors and editable grid before submit        |
| Missing keyword coverage       | Phase 3 classification errors | Rule validation endpoint and admin CRUD for keywords      |
| Stale cache after rule changes | Incorrect classification      | Versioned context + explicit cache invalidation (Phase 3) |
| Duplicate active keyword rules | Conflict and ambiguity        | Partial unique index on active rows only                  |
| Slow import endpoint           | Poor UX                       | Latency warnings + observability endpoints (Phase 3)      |

---

## 12. Deployment Architecture

Environments:

- Development: local frontend + local backend + local PostgreSQL
- Production: same pattern with production hosts and secured config

Deployment diagram:

```text
┌──────────────────────────────────────────────────────────────┐
│                        Environment                           │
├──────────────────────────────────────────────────────────────┤
│  Browser                                                     │
│    │                                                         │
│    ▼                                                         │
│  Frontend (React/Vite)                                       │
│    │ HTTP                                                    │
│    ▼                                                         │
│  Backend (FastAPI)                                           │
│    │ SQL                                                     │
│    ▼                                                         │
│  PostgreSQL                                                  │
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

Admin observability endpoints (Phase 3):

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
- `docs/system_patterns.md` (includes Phase 3 patterns)
- `docs/system_architectural.md` (includes Phase 3 endpoints)
- `incident_reports/` (Phase 3 incident documentation)

---

## 16. Beginner Glossary

- **Parser:** Code that reads a file and turns it into structured rows.
- **Normalization:** Making data consistent (same columns, same date format, clean amount values).
- **Merchant Normalization (Phase 3):** Preprocessing step that cleans transaction notes before classification (e.g., "MCDONALDS #123" → "mcdonalds").
- **Classification engine:** Logic that decides which category a transaction belongs to.
- **Soft delete:** Mark a row as inactive instead of physically removing it.
- **Feature Flag (Phase 3):** Runtime toggle that enables/disables optional functionality like merchant normalization.
- **Observability (Phase 3):** Logs/metrics/alerts that help us understand system behavior and detect issues.
- **Cache:** Temporary in-memory data used to speed up repeated operations.
