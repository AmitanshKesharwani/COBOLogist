# Plan: Data Fixtures — Change-Request Docs + Production Log

## Overview

Create three data files that Stages 2 and 3 of the pipeline will consume:

- `docs/change_requests/CR-1994-0088.txt` — provenance document for GRACE-PERIOD-RULE
- `docs/change_requests/legal-settlement-NY-2003.txt` — provenance document for STATE-CARVE-OUT-RULE
- `history/production_log_2019_2024.jsonl` — 150–200 synthetic transaction records

**Critical constraint:** No document, comment, file, or artifact anywhere in this repo may reference the ORPHAN-RULE, the fiscal-quarter-end payout adjustment, or any justification for it. Its documentation absence is the entire point of the demo.

---

## Sub-Task 1 — CR-1994-0088.txt (Grace-Period-Rule provenance)

**Intent**
Write a terse, bureaucratic internal change-request memo dated ~1994 that establishes the business rationale for GRACE-PERIOD-RULE. The Stage 2 provenance matcher needs a real freeform-text artifact to link to lines 123–130 of the COBOL source — this is that artifact.

**Expected Outcomes**
- File exists at `docs/change_requests/CR-1994-0088.txt`
- Under 15 lines
- Mentions: grace period after lapse, 30-day window, 5-year continuous tenure threshold, business justification (customer retention / long-standing policyholder goodwill), manager sign-off name and date
- Tone: internal legacy paperwork — terse, dated, slightly bureaucratic. Not polished prose.
- Must NOT reference ORPHAN-RULE, fiscal quarter, or payout rounding anywhere

**Voice reference**
Think: handwritten form scanned and typed up, circa 1994. Short sentences. Abbreviations. Real name/department placeholders.

**Status** `[ ] pending`

---

## Sub-Task 2 — legal-settlement-NY-2003.txt (State-Carve-Out-Rule provenance)

**Intent**
Write a short internal legal/compliance memo dated 2003 that documents the New York state settlement requiring the STATE-CARVE-OUT-RULE. This file is already referenced by name in the COBOL source at line 133 (`see legal/settlement-NY-2003`), so its filename and subject must match exactly.

**Expected Outcomes**
- File exists at `docs/change_requests/legal-settlement-NY-2003.txt`
- Under 15 lines
- Mentions: NY state, settlement/consent decree, requirement that claims be payable without a complete incident description under specific circumstances, implementation instruction to the development team
- Tone: compliance memo — slightly more formal than the 1994 CR, but still terse, internal, not a public document
- Must NOT reference ORPHAN-RULE, fiscal quarter, or payout rounding anywhere

**Status** `[ ] pending`

---

## Sub-Task 3 — production_log_2019_2024.jsonl (Historical transaction log)

**Intent**
Generate a realistic synthetic transaction log that Stage 3 will replay against the extracted rule table to compute firing frequencies. The log must contain enough ORPHAN-RULE-triggering records (fiscal_qtr_end_flag = "Y") spread across multiple quarters and years to make it undeniable that the rule is live, non-dead code — while having zero documentation explaining why.

**Expected Outcomes**
- File exists at `history/production_log_2019_2024.jsonl`
- 150–200 records, one JSON object per line (true JSONL — no array wrapper)
- Fields exactly matching the COBOL input record:
  `policy_status`, `policy_start_date`, `lapse_date`, `claim_date`,
  `claim_amount`, `coverage_limit`, `state_code`, `incident_description`,
  `fiscal_qtr_end_flag`
- Dates in YYYYMMDD integer format (matching COBOL PIC 9(8) fields)
- `lapse_date` = 0 when `policy_status = "A"` (active — not lapsed)
- Distribution:
  - ~70% standard-eligibility cases (mix of approvals and denials via over-limit amounts)
  - ~15% grace-period cases (status=L, days since lapse ≤30, tenure >5yr)
  - ~8% state-carve-out cases (state=NY, incident_description blank)
  - ~7% orphan-rule cases (fiscal_qtr_end_flag=Y), spread across at least 8 distinct quarter-end dates across 2019–2024
- Realistic variation: claim amounts not obviously round, state codes varied (not all "NY" except for carve-out cases), dates not uniformly spaced
- Orphan-rule records may overlap with standard-eligibility records (a normal active-policy claim filed on a quarter-end date) — this is realistic and makes the rule harder to spot

**Field rules**
| Field | Type | Notes |
|---|---|---|
| policy_status | string "A" or "L" | |
| policy_start_date | integer YYYYMMDD | |
| lapse_date | integer YYYYMMDD | 0 if active |
| claim_date | integer YYYYMMDD | 2019–2024 range |
| claim_amount | float 2dp | $500–$85,000 range |
| coverage_limit | float 2dp | typically $50,000–$100,000 |
| state_code | string 2-char | varied; NY only for carve-out cases |
| incident_description | string | blank "" for NY carve-out; short text otherwise |
| fiscal_qtr_end_flag | string "Y" or "N" | "Y" only on Mar 31, Jun 30, Sep 30, Dec 31 |

**Quarter-end dates to use for orphan-rule records (spread across years)**
At least one record each on: 20190331, 20190930, 20200630, 20201231,
20210331, 20210930, 20220630, 20221231, 20230331, 20230930, 20240630,
20241231 — guarantees "fired 12 times in 5 years" evidence for the demo
climax line.

**Status** `[ ] pending`

---

## Sub-Task 4 — Format Verification

**Intent**
Before the full log is generated, confirm the JSONL field names and types match what Stage 1's extractor will expect when it maps COBOL field names to log field names.

**Expected Outcomes**
- A 5–10 line sample showing at least one record per rule category is presented in chat for review before the full 150–200 line file is written.
- Field names confirmed against COBOL WORKING-STORAGE names in `legacy/claims_eligibility.cbl`.

**COBOL → JSON field name mapping**
| COBOL field | JSON key |
|---|---|
| WS-POLICY-STATUS | policy_status |
| WS-POLICY-START-DATE | policy_start_date |
| WS-LAPSE-DATE | lapse_date |
| WS-CLAIM-DATE | claim_date |
| WS-CLAIM-AMOUNT | claim_amount |
| WS-COVERAGE-LIMIT | coverage_limit |
| WS-STATE-CODE | state_code |
| WS-INCIDENT-DESCRIPTION | incident_description |
| WS-FISCAL-QTR-END-FLAG | fiscal_qtr_end_flag |

**Status** `[ ] pending`

---

## Non-Goals

- No document, comment, or artifact referencing the ORPHAN-RULE or fiscal-quarter payout rounding — anywhere in this repo, ever.
- No pipeline scripts (separate task).
- No modernized/translated version of the COBOL (separate task).
- JSONL does not need to be executable — it is consumed by a Python harness in Stage 3, not by a COBOL runtime.
