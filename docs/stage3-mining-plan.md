# Plan: Stage 3 — Golden Dataset Mining (pipeline/mine_golden_dataset.py)

## Overview

Create `pipeline/mine_golden_dataset.py`: a deterministic Python script that
reads `pipeline/output/provenance.json` and `history/production_log_2019_2024.jsonl`,
evaluates each rule's boolean condition against every historical record, and writes
`pipeline/output/firing_frequency.json` — one entry per rule augmenting the Stage 2
provenance table with empirical firing evidence from the production log.

No LLM is involved at any point. This stage is pure computation: counting, grouping,
and frequency analysis over structured data.

**Verified expected counts (independently confirmed against the full 147-record log):**

| Rule | times_fired | distinct_years_fired | Notes |
|---|---|---|---|
| STANDARD-ELIGIBILITY-RULE | 112 | — | 129 A-status records minus 17 over-limit |
| GRACE-PERIOD-RULE | 17 | — | All 18 L-status records except line 104 (raw diff=186) |
| STATE-CARVE-OUT-RULE | 8 | — | Lines 99–106: NY + empty description |
| ORPHAN-RULE | 18 | 6 | Quarter-end dates across 2019–2024 |

---

## Sub-Task 1 — File I/O and record loading

**Intent**
Read the two input files and load them into in-memory structures. Provenance entries
provide rule metadata; the JSONL log provides the transaction records to evaluate.

**Expected Outcomes**
- `provenance.json` loaded as a list of 4 rule dicts (same structure as Stage 2 output).
- `production_log_2019_2024.jsonl` loaded as a list of dicts, one per non-blank line,
  preserving 1-based line numbers for the `sample_record_lines` field.
- The loader must skip blank/empty lines without error (line 148 is blank in the file).

**Todo List**
- [ ] Define `PROVENANCE_FILE`, `LOG_FILE`, `OUTPUT_FILE` path constants (relative to
  project root, matching the convention in Stage 1 and Stage 2).
- [ ] Load provenance with `json.loads(path.read_text())`.
- [ ] Load JSONL line-by-line; parse each non-blank line with `json.loads`; store
  alongside its 1-based line number.

**Relevant Context**
- `pipeline/output/provenance.json` — 4 entries; schema defined in Stage 2.
- `history/production_log_2019_2024.jsonl` — 147 records + 1 blank line (line 148).
- Pattern: both Stage 1 (`extract_rules.py`) and Stage 2 (`recover_provenance.py`)
  use `pathlib.Path` for all file I/O — follow the same convention.

**Status** `[ ] pending`

---

## Sub-Task 2 — Rule condition evaluators

**Intent**
Implement each rule's condition as a standalone Python boolean function. These
functions must exactly replicate the COBOL arithmetic (raw YYYYMMDD integer
subtraction, year extraction via `// 10000`) and match the conditions already
implemented in `modern/claims_eligibility.py` — no new interpretation of the
business logic is introduced here.

**Expected Outcomes**
- One Python function per rule, each accepting a single record dict and returning bool.
- The four evaluators, with their exact conditions:

| Rule | Python condition |
|---|---|
| STANDARD-ELIGIBILITY-RULE | `r["policy_status"] == "A" and r["claim_amount"] <= r["coverage_limit"]` |
| GRACE-PERIOD-RULE | `r["policy_status"] == "L" and (r["claim_date"] - r["lapse_date"]) <= 30 and (r["lapse_date"] // 10000 - r["policy_start_date"] // 10000) > 5` |
| STATE-CARVE-OUT-RULE | `r["state_code"] == "NY" and r["incident_description"].strip() == ""` |
| ORPHAN-RULE | `r["fiscal_qtr_end_flag"] == "Y"` |

- A-status records with `lapse_date = 0` will produce a large negative or
  nonsensical value for `days_since_lapse` when the L-status condition is applied,
  but the `policy_status == "L"` guard ensures they never reach the arithmetic — no
  special-casing is needed.

**Important:** Rules are evaluated independently and non-exclusively. A single record
CAN fire multiple rules simultaneously (e.g. line 3: status=A, amount≤limit,
fiscal_qtr_end_flag=Y → fires both STANDARD and ORPHAN). The script must NOT
implement any early-exit or mutual-exclusion logic.

**Relevant Context**
- `modern/claims_eligibility.py` lines 37–42, 45, 50, 55 — exact Python arithmetic
  already established; mine_golden_dataset.py must use the same expressions.
- `legacy/claims_eligibility.cbl` lines 85–96 — COBOL arithmetic these replicate.

**Status** `[ ] pending`

---

## Sub-Task 3 — Firing frequency computation

**Intent**
For each rule, iterate all records, apply the rule's evaluator, and accumulate the
required statistics. This is the core computation of Stage 3.

**Expected Outcomes**
For each rule, produce:
- `times_fired` — count of records where the condition is true.
- `distinct_years_fired` — count of distinct calendar years (extracted as
  `claim_date // 10000`) across all firing records.
- `first_fired` — lowest `claim_date` integer value among firing records (or `null`
  if `times_fired == 0`).
- `last_fired` — highest `claim_date` integer value among firing records (or `null`
  if `times_fired == 0`).
- `sample_record_lines` — 1-based line numbers of up to the first 3 firing records
  (by order of appearance in the log, not by date).

**Todo List**
- [ ] For each rule entry from provenance, initialise accumulators: `fired_lines`,
  `fired_dates`.
- [ ] Iterate records; evaluate the corresponding condition function; if true, append
  line number to `fired_lines`, append `claim_date` to `fired_dates`.
- [ ] After the loop: compute `times_fired = len(fired_lines)`,
  `distinct_years_fired = len({d // 10000 for d in fired_dates})`,
  `first_fired = min(fired_dates) or null`, `last_fired = max(fired_dates) or null`,
  `sample_record_lines = fired_lines[:3]`.

**Relevant Context**
- Calendar year extraction: `claim_date // 10000` — consistent with how
  `WS-START-YEAR` and `WS-LAPSE-YEAR` are computed in the COBOL.
- `sample_record_lines` is for spot-checking only; using the first 3 by file order
  (not sorted by date) is the simplest and most auditable choice.

**Status** `[ ] pending`

---

## Sub-Task 4 — JSON output

**Intent**
Merge the firing statistics into the provenance entries and write the result to
`pipeline/output/firing_frequency.json`. This file is the Stage 3 output artifact
consumed by Stage 4.

**Expected Outcomes**
- Output is a JSON array of 4 objects, each being the full provenance entry from
  Stage 2 extended with the 5 new firing fields.
- Schema per entry:

```json
{
  "rule_id": "R4",
  "paragraph_name": "ORPHAN-RULE",
  "source_line_start": 146,
  "source_line_end": 151,
  "condition_text": "...",
  "action_text": "...",
  "comment_text": null,
  "provenance_status": "Unknown",
  "matched_document": null,
  "matched_excerpt": null,
  "confidence_note": "...",
  "times_fired": 18,
  "distinct_years_fired": 6,
  "first_fired": 20190331,
  "last_fired": 20241231,
  "sample_record_lines": [3, 8, 12]
}
```

- File written with `json.dumps(..., indent=2)`.
- Parent directory created with `mkdir(parents=True, exist_ok=True)` if absent
  (matches Stage 1 and Stage 2 convention).

**Todo List**
- [ ] Merge each provenance entry dict with its corresponding firing stats dict using
  `{**provenance_entry, **firing_stats}`.
- [ ] Write the merged list to `pipeline/output/firing_frequency.json`.
- [ ] Print a human-readable summary to stdout for each rule:
  `rule_id  paragraph_name  times_fired  distinct_years_fired`.

**Status** `[ ] pending`

---

## Sub-Task 5 — Docstring and design-contract notice

**Intent**
Add the required top-of-file docstring that makes the LLM/deterministic contract
explicit, consistent with Stage 1 and Stage 2 notices.

**Expected Outcomes**
- Module docstring contains exactly:
  "Stage 3 — zero LLM involvement, pure deterministic computation. Every rule's
  condition is evaluated directly against logged data; there is no judgment call
  in this stage."
- Configuration block documents the three path constants and the evaluator map.

**Relevant Context**
- Stage 1 docstring: scope/boundary notice at top of `pipeline/extract_rules.py` lines 1–17.
- Stage 2 docstring: LLM reasoning notice at top of `pipeline/recover_provenance.py` lines 1–33.
- Tone and format should match the existing two scripts.

**Status** `[ ] pending`

---

## Non-Goals

- No LLM calls of any kind.
- No modification of `provenance.json`, `rules.json`, or the JSONL log.
- No interpretation of *why* a rule fired — that is Stage 4's job.
- No Stage 4 divergence logic (comparing legacy vs. modern outputs) — separate task.
- No handling of malformed records (the fixture log is well-formed by construction).
