# Incident Report: Incorrect Transaction Categorization Due to Normalization Failure

**Project:** Data Normalization & Categorization Engine Version 1
**Date:** 2026-04-27
**Reporter:** Technical Support / Backend Engineering

---

## 1. Executive Summary

A customer-facing import workflow failed to classify transactions correctly because the backend classification pipeline did not normalize merchant notes strongly enough before rule matching. The incident surfaced as repeated Phase 3 failures in `/transactions/import`, with notes like `"MCDONALDS #123"` failing to match existing category rules.

This report covers the real system flow, evidence from the backend logic, root cause analysis, and improvement proposals that include both support investigation and backend engineering fixes.

---

## 2. System Context

The version 1 system consists of:

- Frontend: React + Vite editor workflow in `frontend/src/NormalizedData.tsx`
- Backend: FastAPI service in `backend/main.py`
- Database: PostgreSQL schema in `backend/database_setup.sql`

Key backend paths involved:

- `POST /parse` — upload and parse CSV/Excel/JSON/TXT, then normalize dates
- `POST /transactions/import` — import normalized rows and classify categories
- `POST /category-keywords/validate-note` — validate note text against classifier
- `GET /admin/observability/alerts` — track import failures and Phase 3 fallback alerts
- `POST /admin/merchant-normalization-rules/validate-note` — test merchant note normalization

The classification engine uses `determine_category_id(...)` in `backend/main.py`.

---

## 3. Impact

- Transactions failed to import or were assigned to the wrong category.
- Users saw backend errors such as:
  - `Cannot automatically determine category for 'MCDONALDS #123'. Available keywords: ...`
- Import observability can generate alert states when many rows hit Phase 3.
- This affects both the finance pipeline and user confidence in transaction categorization.

---

## 4. Investigation Timeline

1. User reported a failed import with several vendor notes not classified.
2. Support reproduced the issue with `POST /transactions/import?debug=true`.
3. Backend request returned a Phase 3 failure and listed available keywords.
4. Support confirmed the failure point was `determine_category_id(...)` after input normalization.
5. Backend logic review showed weak merchant note normalization and limited keyword coverage.
6. Support verified observability via `/admin/observability/alerts`.

---

## 5. Findings

### 5.1 Actual backend behavior

The backend classification flow in `backend/main.py` is:

- load category keywords and names via `get_classification_context(...)`
- optionally normalize merchant note if `merchant_normalization_enabled` is true
- call `determine_category_id(...)`
- insert transaction and optionally log to `transaction_classification_log`

### 5.2 Real code evidence

The classification function uses three phases:

```python
# Phase 1: keyword match
if matched_keywords_by_category:
    best_match = min(matched_keywords_by_category.items(), key=lambda item: (item[1][1], item[0]))
    category_id = best_match[0]

# Phase 2: category-name fallback
for category_name, category_id in all_category_names.items():
    if category_name in note_lower:
        return category_id

# Phase 3: no match => error
raise HTTPException(status_code=400, detail=error_detail)
```

The problem is that the note is only normalized to lower case and stripped, and merchant normalization rules are optional.

### 5.3 Likely fault pattern

The note `"MCDONALDS #123"` does not contain any seeded keyword such as `restaurant`, `coffee`, `cafe`, or `alfamart`, and does not contain a category name like `Food & Dining`. As a result, Phase 3 is reached.

If merchant normalization is disabled, the system does not normalize brand variants or strip transaction metadata.

---

## 6. Root Cause Scenarios

This incident is strongest when described as a single root cause with related failure modes.

### Primary root cause: String normalization failure

The system receives notes with noisy branding and identifiers, but the rule engine only checks raw lowercase substring matches.

Example failure mode:

- Input note: `MCDONALDS #123`
- Current normalization: `note.lower().strip()`
- Keyword rules expected: `restaurant`, `coffee`, `cafe`
- Result: no match → Phase 3 failure

This is a substantive and realistic support incident because it shows a real data pipeline gap: noisy transaction text is common in bank statements.

### Secondary root cause: Missing or incomplete merchant alias rules

The backend supports feature-flagged merchant normalization rules, but the default seeded rules are limited to Indonesian stores like `indomaret`, `alfamart`, and ride-sharing tokens.

A note containing a global merchant alias such as `mcdonalds`, `mcdo`, or `mcd` is not covered, so the classifier cannot map it to `Food & Dining`.

### Tertiary root cause: Input mapping and header variation

Although the frontend includes a mapping step, inconsistent source formats still matter in support investigations:

- Users may upload CSVs with headers such as `merchant`, `description`, `detail`, or `transaction_info`.
- The backend parse stage normalizes dates but does not normalize headers beyond the front-end mapping layer.

This is a good follow-up incident for support: a file may appear parsed correctly, yet the wrong columns are mapped or ignored.

---

## 7. Evidence and Reproduction

### 7.1 API reproduction example

**Request Method:**

Bash

```bash
cat <<EOF > test_payload.json
[
  {
    "date": "2026-04-15",
    "note": "MCDONALDS #123",
    "amount": -15.75
  }
]
EOF

curl.exe -X POST "https://data-normalization-and-categorization.onrender.com/transactions/import?debug=true" \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

Powershell

```
@'
[{"date":"2026-04-15","note":"MCDONALDS #123","amount":-15.75}]
'@ | Set-Content -Path test_payload.json

curl.exe -X POST "https://data-normalization-and-categorization.onrender.com/transactions/import?debug=true" `
  -H "Content-Type: application/json" `
  -d "@test_payload.json"
```

Postman

```bash
URL:
https://data-normalization-and-categorization.onrender.com/transactions/import?debug=true
Headers:
Content-Type: application/json
Body:
[
  {
    "date": "2026-04-15",
    "note": "MCDONALDS #123",
    "amount": -15.75
  }
]
```

**Expected classification path:**

- `normalize_merchant_note(...)` should produce a normalized note such as `mcdonalds`
- `determine_category_id(...)` should match `restaurant` or `mcdonalds` alias

**Observed response:**

```json
{
  "detail": "Cannot automatically determine category for 'MCDONALDS #123'. Available keywords: alfamart, bpjs, cafe, coffee, fuel, grab, indomaret, restaurant, taxi. You can also include a category name like Entertainment, Food & Dining, Healthcare, Investments, Salary, Transportation, Utilities."
}
```

### 7.2 Debug endpoint evidence

Using the existing debug mode provides direct proof of classification state. Example response from `POST /transactions/import?debug=true` since the incident simulation with "MCDONALDS #123", you get the Phase 3 error instead, because the note fails classification :

```json
{
  "inserted": 0,
  "classifications": [],
  "merchant_normalization_enabled": false,
  "observability": {
    "classification_failure_rate": 100.0,
    "phase3_fallback_rate": 100.0
  }
}
```

The success case would be look like:

```bash
[{"date":"2026-04-15","note":"restaurant","amount":-15.75}]

{
  "inserted": 1,
  "classifications": [
    {
      "note": "restaurant",
      "normalized_note": "restaurant",
      "amount": -15.75,
      "category_id": 4,
      "category_name": "Food & Dining",
      "phase": 1,
      "resolution_path": "keyword_match",
      "matched_keyword": "restaurant",
      "match_type": "substring",
      "priority": 1
    }
  ],
  "merchant_normalization_enabled": false,
  "observability": {
    "classification_failure_rate": 0.0,
    "phase3_fallback_rate": 0.0
  }
}
```

### 7.3 Observability evidence

The backend supports rolling alerts via `/admin/observability/alerts`. A real incident can be confirmed with:

```bash
curl.exe "https://data-normalization-and-categorization.onrender.com/admin/observability/alerts"
```

Which can show alerts such as:

- `Phase 3 fallback rate exceeded threshold`
- `Classification failure rate exceeded threshold`

These are real operational signals in the system.

### 7.4 Note validation evidence

Support can validate candidate notes with: `POST /category-keywords/validate-note`.

Example:

```bash
curl.exe -X POST "https://data-normalization-and-categorization.onrender.com/category-keywords/validate-note" \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-04-15","note":"MCDONALDS #123","amount":-15.75}'
```

Output:

```bash
{
  "classification_scope":"global",
  "cache_meta":{"source":"cache",
  "version":10,"rebuilt_at":"2026-04-28T08:32:06.300487Z"},
  "merchant_normalization_enabled":false,
  "normalized_note":"MCDONALDS #123",
  "classification":{
    "phase":3,
    "resolution_path":"error_no_match",
    "matched_keyword":null,"match_type":null,
    "priority":null,
    "error_message":"Cannot automatically determine category for 'MCDONALDS #123'. Available keywords: alfamart, bpjs, bus, cafe, coffee, fuel, grab, indomaret, restaurant, taxi, uber. You can also include a category name like Entertainment, Food & Dining, Freelance, Healthcare, Investments, Salary, Test CORS, Test Category, Transportation, Utilities in the note.",
    "available_keywords":[
    "alfamart","bpjs","bus","cafe","coffee","fuel","grab","indomaret","restaurant","taxi","uber"
    ],
    "available_categories":[
    "Entertainment","Food & Dining","Freelance","Healthcare","Investments","Salary","Test CORS","Test Category","Transportation","Utilities"
    ]
  }
}
```

A failing result demonstrates that the note path is broken before import.

---

## 8. Proposed Fixes

This incident should be documented with both a support investigation and one or more backend engineering fixes.

### 8.1 Immediate support fix

- Enable `merchant_normalization_enabled` via `/admin/feature-flags/merchant-normalization`
- Add merchant normalization rules for common aliases such as `mcdonalds`, `mcdo`, `mcd`, and `mcdonald` with `match_type=word_boundary`
- Re-run `POST /category-keywords/validate-note` to confirm alias mapping

This is a realistic technical support action: use admin toggles and rule validation first.

### 8.2 Backend engineering fix (recommended)

#### Fix 1: strengthen merchant note normalization

Current implementation in `backend/main.py`:

```python
normalized = (note or "").lower().strip()
for rule in rules:
    normalized = _apply_normalization_rule(...)
```

Better implementation:

```python
def normalize_transaction_note(note: str, rules: List[Dict[str, Any]]) -> str:
    normalized = (note or "").lower().strip()
    normalized = re.sub(r"\s+#\d+", "", normalized)  # remove trailing IDs
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)  # normalize punctuation
    normalized = re.sub(r"\s+", " ", normalized)
    for rule in rules:
        pattern = rule["pattern"].lower().strip()
        replacement = rule["replacement"].lower().strip()
        normalized = _apply_normalization_rule(normalized, pattern, replacement, rule["match_type"])
    return normalized.strip()
```

This would normalize notes like `MCDONALDS #123` into a canonical token before classification.

#### Fix 2: add alias-based normalization rules

Create rules such as:

- pattern: `mcdonalds`, replacement: `mcdonalds`, match_type: `word_boundary`
- pattern: `mcdo`, replacement: `mcdonalds`, match_type: `word_boundary`
- pattern: `mcd`, replacement: `mcdonalds`, match_type: `word_boundary`

This directly addresses merchant alias coverage.

#### Fix 3: improve fallback category-name matching

Current fallback only checks raw category name substrings:

```python
for category_name, category_id in all_category_names.items():
    if category_name in note_lower:
```

A stronger approach is to normalize both note and category names before matching, or allow synonym lists for categories like `Food & Dining`.

### 8.3 Longer-term engineering proposal

#### Proposal: add a preprocessing layer before the classifier

Implement a dedicated `normalize_transaction_input(...)` layer that performs:

- header normalization for uploaded files
- note token cleanup and alias mapping
- currency sign and amount extraction consistency
- fallback keyword enrichment for common payment vendors

This would make the system more robust to real-world data while preserving the current rule engine.

#### Proposal: capture incident metadata in `transaction_classification_log`

The backend already stores classification logs when enabled. Use this log for incident replay and root-cause analysis by adding a dashboard or SQL query to inspect:

- `phase_matched`
- `matched_keyword`
- `error_message`
- `note_hash`

That makes support triage more concrete.

---

## 9. Recommended Next Steps

1. Create a minimal support playbook for this incident:
   - reproduce with `POST /transactions/import?debug=true`
   - validate note with `/category-keywords/validate-note`
   - inspect `/admin/observability/alerts`
   - enable merchant normalization if needed
2. Add at least one merchant alias rule for global vendors in the current keyword system.
3. Implement the stronger normalization helper described above.
4. Add a regression test around `MCDONALDS #123` and similar alias notes.
5. Document the incident in the project repository under `docs/incident_reports/`.

---

## 10. Incident Summary for Interview Use

This incident is especially strong because it combines:

- messy real-world transaction text
- multi-stage system flow (parse → normalize → classify → persist)
- both support and engineering investigation
- clear improvement opportunities

It is a credible case to present as a Backend or Technical Support engineer because it demonstrates how you traced the failure through multiple system stages and proposed both immediate mitigation and an engineering fix.
