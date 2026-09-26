# Plan: Legacy COBOL Fixture — claims_eligibility.cbl

## Overview

Create `legacy/claims_eligibility.cbl`, a small but realistic COBOL claims-eligibility program that serves as the demo fixture for the Legacy Provenance Engine pipeline. The file is the single source of truth for all four pipeline stages: Stage 1 extracts rules from it, Stage 3 replays transactions against it, Stage 4 diffs it against the modern translation.

The program must contain exactly four rules, each in its own named paragraph, with clean structural boundaries so a static parser can locate rule start/end by paragraph name alone. Compiler correctness is a non-goal; structural clarity and realistic COBOL style are the goals.

---

## Sub-Task 1 — Define the Data Layout

**Intent**  
Establish the WORKING-STORAGE and LINKAGE (or FILE) record definitions that all four rules will read from and write to. These definitions are the "schema" the static extractor will reference when it resolves variable names in rule conditions.

**Expected Outcomes**  
- A single input record containing all fields required by the four rules: policy status, policy start date, lapse date, claim date, claim amount, coverage limit, state code, incident description, and fiscal-quarter-end flag.
- A single output record: payable flag (Y/N) and payout amount.
- Field names that are unambiguous and self-documenting (e.g., `WS-POLICY-STATUS`, `WS-CLAIM-AMOUNT`).

**Todo List**  
- [ ] Define `WS-POLICY-STATUS` PIC X(1): values `A` (active) or `L` (lapsed).
- [ ] Define `WS-POLICY-START-DATE` PIC 9(8) YYYYMMDD format.
- [ ] Define `WS-LAPSE-DATE` PIC 9(8), zero-filled when policy is active.
- [ ] Define `WS-CLAIM-DATE` PIC 9(8).
- [ ] Define `WS-CLAIM-AMOUNT` PIC 9(7)V99 COMP-3.
- [ ] Define `WS-COVERAGE-LIMIT` PIC 9(7)V99 COMP-3.
- [ ] Define `WS-STATE-CODE` PIC X(2).
- [ ] Define `WS-INCIDENT-DESCRIPTION` PIC X(100).
- [ ] Define `WS-FISCAL-QTR-END-FLAG` PIC X(1): value `Y` when claim date is last day of a fiscal quarter.
- [ ] Define `WS-DAYS-SINCE-LAPSE` PIC 9(4) as a computed working variable.
- [ ] Define `WS-POLICY-TENURE-YEARS` PIC 9(3) as a computed working variable.
- [ ] Define output: `WS-PAYABLE` PIC X(1), `WS-PAYOUT-AMOUNT` PIC 9(7)V99 COMP-3.

**Relevant Context**  
- All four rules reference subsets of these fields; the full set is the union of all rule requirements.
- `WS-DAYS-SINCE-LAPSE` and `WS-POLICY-TENURE-YEARS` are scratch variables computed in the PROCEDURE DIVISION before the rule paragraphs run — this keeps the rule conditions clean and readable for the static extractor.
- `WS-FISCAL-QTR-END-FLAG` is set externally (by the test harness/transaction log) — the COBOL program just reads it. This keeps the orphan rule's condition a simple flag test rather than complex date arithmetic.

**Status** `[ ] pending`

---

## Sub-Task 2 — Write the Four Rule Paragraphs

**Intent**  
Write one named COBOL paragraph per rule, in order, each doing exactly one thing: evaluate its condition and, if true, set `WS-PAYABLE` and/or `WS-PAYOUT-AMOUNT` and then `GO TO EVALUATE-DONE`. This makes rule boundaries structurally unambiguous.

**Expected Outcomes**  
- Four paragraphs with these exact names:
  1. `STANDARD-ELIGIBILITY-RULE`
  2. `GRACE-PERIOD-RULE`
  3. `STATE-CARVE-OUT-RULE`
  4. `ORPHAN-RULE`
- Each paragraph is terminated by a `GO TO EVALUATE-DONE` (or `CONTINUE` to fall through) so the static extractor sees a clean exit.
- Comments on Grace-Period and State-Carve-Out paragraphs exactly as specified; zero comments on Orphan Rule.

**Rule Specifications**

| # | Paragraph | Condition | Action | Comments |
|---|-----------|-----------|--------|----------|
| 1 | `STANDARD-ELIGIBILITY-RULE` | `WS-POLICY-STATUS = 'A'` AND `WS-CLAIM-AMOUNT <= WS-COVERAGE-LIMIT` | `WS-PAYABLE = 'Y'`, `WS-PAYOUT-AMOUNT = WS-CLAIM-AMOUNT` | None |
| 2 | `GRACE-PERIOD-RULE` | `WS-POLICY-STATUS = 'L'` AND `WS-DAYS-SINCE-LAPSE <= 30` AND `WS-POLICY-TENURE-YEARS > 5` | `WS-PAYABLE = 'Y'`, `WS-PAYOUT-AMOUNT = WS-CLAIM-AMOUNT` | "grandfather clause for long-tenured policyholders" |
| 3 | `STATE-CARVE-OUT-RULE` | `WS-STATE-CODE = 'NY'` AND `WS-INCIDENT-DESCRIPTION = SPACES` | `WS-PAYABLE = 'Y'`, `WS-PAYOUT-AMOUNT = WS-CLAIM-AMOUNT` | vague reference to "2003 settlement requirement" |
| 4 | `ORPHAN-RULE` | `WS-FISCAL-QTR-END-FLAG = 'Y'` | `WS-PAYOUT-AMOUNT = WS-PAYOUT-AMOUNT * 1.005` (rounding adjustment) | None — no comment, no explanation |

**Todo List**  
- [ ] Write `STANDARD-ELIGIBILITY-RULE` paragraph with clean IF/MOVE/GO TO structure.
- [ ] Write `GRACE-PERIOD-RULE` paragraph with the grandfather-clause comment block above it.
- [ ] Write `STATE-CARVE-OUT-RULE` paragraph with the 2003-settlement comment above it.
- [ ] Write `ORPHAN-RULE` paragraph — no comment, just the condition and payout-adjustment COMPUTE.
- [ ] Add `EVALUATE-DONE` paragraph at the end as the common exit point.

**Relevant Context**  
- The orphan rule fires *after* payability is already set (it adjusts the payout amount, not the Y/N flag). This means a modern translation that drops the rule passes a simple payable/not-payable check but fails a payout-amount diff — making it the perfect silent bug for Stage 4.
- `GO TO` usage is deliberate and realistic for legacy COBOL; the static extractor will use it as a paragraph-boundary signal.

**Status** `[ ] pending`

---

## Sub-Task 3 — Wire the PROCEDURE DIVISION Driver

**Intent**  
Write the main procedure that computes the two scratch variables (`WS-DAYS-SINCE-LAPSE`, `WS-POLICY-TENURE-YEARS`) and then calls the four rule paragraphs in order via `PERFORM`. This is the scaffolding that makes the program runnable by the Stage 3 test harness.

**Expected Outcomes**  
- A `MAIN-PROCEDURE` paragraph that initializes outputs, computes scratch variables, and then performs each rule paragraph in sequence.
- The program terminates with `STOP RUN`.
- Scratch variable computation is simple enough to be parsed visually (e.g., subtract dates using integer arithmetic on YYYYMMDD values divided by 10000 for the year component).

**Todo List**  
- [ ] Write `MAIN-PROCEDURE` paragraph.
- [ ] Initialize `WS-PAYABLE = 'N'` and `WS-PAYOUT-AMOUNT = 0` at start.
- [ ] Compute `WS-DAYS-SINCE-LAPSE` from `WS-CLAIM-DATE` and `WS-LAPSE-DATE` (simple integer subtraction, realistic enough for fixture purposes).
- [ ] Compute `WS-POLICY-TENURE-YEARS` from `WS-POLICY-START-DATE` and `WS-LAPSE-DATE`.
- [ ] PERFORM each of the four rule paragraphs in order.
- [ ] Add `STOP RUN`.

**Relevant Context**  
- Date arithmetic in real COBOL uses intrinsic functions (`FUNCTION INTEGER-OF-DATE`). For the fixture, simple YYYYMMDD integer subtraction divided by 10000 is close enough and keeps the code readable.
- The PERFORM order determines rule priority: Standard first, then Grace Period, then State Carve-Out, then Orphan. The first rule to set `WS-PAYABLE = 'Y'` wins for the Y/N flag; the Orphan Rule adjusts payout amount regardless.

**Status** `[ ] pending`

---

## Sub-Task 4 — Final Review: Paragraph Name + Line Range Sanity Check

**Intent**  
Verify the finished file is structured so a line-by-line scan can locate each paragraph by name, and document the expected paragraph names and approximate line ranges for the implementer to report back.

**Expected Outcomes**  
- All four paragraph names appear as left-justified labels in Area A (columns 8–11 in standard COBOL layout).
- No paragraph name is a substring of another (avoids false-positive matches in simple grep-based extractors).
- A short summary table of paragraph names and line ranges is produced after the file is written.

**Todo List**  
- [ ] Confirm paragraph names are in Area A format.
- [ ] Confirm no accidental name collisions.
- [ ] After file is written, report back paragraph names and approximate line ranges.

**Status** `[ ] pending`

---

## Non-Goals

- Strict IBM Enterprise COBOL compiler compliance (acceptable to omit COPY books, FD entries, SELECT clauses).
- Handling of invalid/missing input (no validation paragraphs needed).
- More than four rules.
- Any pipeline scripts — this plan is fixture-only.
