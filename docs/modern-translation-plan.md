# Plan: Modernized Translation — modern/claims_eligibility.py

## Overview

Create `modern/claims_eligibility.py`: a Python translation of
`legacy/claims_eligibility.cbl` that faithfully reproduces the behaviour
of STANDARD-ELIGIBILITY-RULE, GRACE-PERIOD-RULE, and STATE-CARVE-OUT-RULE
— including the COBOL's intentionally flawed date arithmetic — while
**silently omitting** ORPHAN-RULE entirely, exactly as would happen in a
real migration where the rule has no documentation.

After writing the file, run a verification script against all 147 records
in `history/production_log_2019_2024.jsonl` and confirm:
- 0 payable-flag mismatches
- exactly 18 payout-amount mismatches (one per fiscal_qtr_end_flag=Y record)

---

## Sub-Task 1 — Replicate the COBOL date arithmetic exactly (flawed)

**Intent**
The COBOL program computes two scratch variables using raw YYYYMMDD integer
subtraction and integer division, not real calendar arithmetic. The Python
translation must reproduce these exact operations — not fix them — so that
the modern version is a faithful behavioural replica on the data we have.

**COBOL arithmetic to replicate:**

```
WS-DAYS-SINCE-LAPSE = WS-CLAIM-DATE - WS-LAPSE-DATE
    (straight integer subtraction of two YYYYMMDD integers)

WS-START-YEAR       = WS-POLICY-START-DATE // 10000
WS-LAPSE-YEAR       = WS-LAPSE-DATE // 10000
WS-POLICY-TENURE-YEARS = WS-LAPSE-YEAR - WS-START-YEAR
```

Note: the fixture was specifically constructed so all grace-period records
keep lapse and claim in the same calendar month — so the integer-subtraction
"days" value is always the actual day count for those records. The Python
must still use the same integer subtraction (not datetime.date arithmetic)
to match the COBOL precisely.

**Python equivalents:**
```python
days_since_lapse    = claim_date - lapse_date          # integer subtraction
start_year          = policy_start_date // 10000
lapse_year          = lapse_date // 10000
policy_tenure_years = lapse_year - start_year
```

**Expected Outcomes**
- A private helper `_compute_scratch(...)` (or inline in `evaluate_claim`)
  that computes these two values exactly as the COBOL does.

**Status** `[ ] pending`

---

## Sub-Task 2 — Implement the three translated rules

**Intent**
Translate STANDARD-ELIGIBILITY-RULE, GRACE-PERIOD-RULE, and
STATE-CARVE-OUT-RULE into Python if-blocks that mirror the COBOL conditions
and actions one-for-one. Rules run in the same order as the COBOL PERFORM
chain: Standard → Grace → Carve-Out. Later rules can overwrite earlier
results, exactly as in the COBOL (no early-exit shortcut unless the COBOL
has one — it doesn't).

**Rule translations:**

| COBOL paragraph | Python condition |
|---|---|
| STANDARD-ELIGIBILITY-RULE | `policy_status == "A" and claim_amount <= coverage_limit` |
| GRACE-PERIOD-RULE | `policy_status == "L" and days_since_lapse <= 30 and policy_tenure_years > 5` |
| STATE-CARVE-OUT-RULE | `state_code == "NY" and incident_description.strip() == ""` |

Action on match (all three rules): `payable = "Y"`, `payout_amount = claim_amount`

**COBOL SPACES equivalence**
`WS-INCIDENT-DESCRIPTION = SPACES` in COBOL matches a field that is
entirely space-filled. The JSON log stores this as `""` (empty string).
`incident_description.strip() == ""` correctly matches both.

**Expected Outcomes**
- Three clearly labelled if-blocks in `evaluate_claim`, each preceded by
  a comment naming the rule (e.g., `# STANDARD-ELIGIBILITY-RULE`).
- No ORPHAN-RULE block, no comment about its absence, no TODO.

**Status** `[ ] pending`

---

## Sub-Task 3 — Function signature and return value

**Intent**
Define `evaluate_claim(...)` to accept the nine input fields as keyword
arguments matching the JSON log field names (which already map 1:1 to
COBOL WS- names), and return a `(payable: str, payout_amount: float)` tuple
so Stage 4 can diff outputs field-by-field without a translation layer.

**Signature:**
```python
def evaluate_claim(
    policy_status: str,
    policy_start_date: int,
    lapse_date: int,
    claim_date: int,
    claim_amount: float,
    coverage_limit: float,
    state_code: str,
    incident_description: str,
    fiscal_qtr_end_flag: str,   # accepted but unused — silent drop
) -> tuple[str, float]:
```

`fiscal_qtr_end_flag` is accepted in the signature (so call sites can pass
the full record dict without filtering) but is never read inside the
function. This is the precise mechanism of the silent drop.

**Expected Outcomes**
- Function signature matches the above exactly.
- Return type is `(str, float)`.
- `fiscal_qtr_end_flag` parameter present but unused.

**Status** `[ ] pending`

---

## Sub-Task 4 — Verification run against the production log

**Intent**
Run `evaluate_claim` against all 147 records in
`history/production_log_2019_2024.jsonl` and compare outputs to a
reference implementation of the full COBOL logic (including ORPHAN-RULE)
to confirm the expected mismatch signature:
- Payable-flag mismatches: **0**
- Payout-amount mismatches: **exactly 18** (one per fiscal_qtr_end_flag=Y)

**Reference implementation**
The verification script will implement COBOL logic inline (including
`payout_amount *= 1.005` when `fiscal_qtr_end_flag == "Y"`) as the
ground-truth "legacy" side, and call `evaluate_claim` as the "modern" side.

**Expected Outcomes**
- Script runs without errors against all 147 records.
- Reports: 0 payable mismatches, 18 payout-amount mismatches.
- If numbers differ, execution stops and discrepancy is reported before
  any further work proceeds.

**Status** `[ ] pending`

---

## Non-Goals

- No pipeline/diffing code (Stage 4 — separate task).
- No fix to the flawed COBOL date arithmetic.
- No documentation or comment anywhere about the missing ORPHAN-RULE.
- No test framework — verification is a one-shot script run inline.
