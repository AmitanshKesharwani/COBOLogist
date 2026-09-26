# Plan: Stage 1 — Rule Extraction (pipeline/extract_rules.py)

## Overview

Create `pipeline/extract_rules.py`: a deterministic static text analyzer
that reads `legacy/claims_eligibility.cbl` and writes
`pipeline/output/rules.json`, a structured table of the four rule
paragraphs.

No LLM is involved. This is pure line-by-line text extraction per the
pipeline's design contract for Stage 1.

Also append a "Known Limitations" section to `docs/PROJECT_OVERVIEW.md`.

---

## What the extractor needs to find

Examining the actual source file (`legacy/claims_eligibility.cbl`):

```
Line 107  STANDARD-ELIGIBILITY-RULE.   ← rule paragraph labels (Area A)
Line 123  GRACE-PERIOD-RULE.
Line 137  STATE-CARVE-OUT-RULE.
Line 146  ORPHAN-RULE.
```

Comment structure before each label:

| Paragraph | Comment type | Comment lines |
|---|---|---|
| STANDARD-ELIGIBILITY-RULE | Post-label divider + inline comment inside body (lines 108-110) | Lines 109-110 |
| GRACE-PERIOD-RULE | Pre-label block (lines 117-122) | Lines 118-121 |
| STATE-CARVE-OUT-RULE | Pre-label block (lines 132-136) | Lines 133-135 |
| ORPHAN-RULE | Pre-label divider only — no semantic comment | null |

**Important distinction:** A bare `*---...---` divider line is not a
semantic comment. `comment_text` should be null when the only lines
before the paragraph label are divider lines. This is the signal that
ORPHAN-RULE has zero documentation.

---

## Sub-Task 1 — Paragraph label detection

**Intent**
Identify the line numbers and names of all rule paragraphs by scanning for
the Area-A label pattern. Exclude `MAIN-PROCEDURE` (not a rule paragraph)
by using an explicit allowlist of the four known rule paragraph names, OR
by scanning only lines after `STANDARD-ELIGIBILITY-RULE` first appears.

**Pattern**
A paragraph label in this file appears as:
```
       PARAGRAPH-NAME.
```
That is: exactly 7 spaces, then an identifier containing only uppercase
letters and hyphens, then a period, then end of significant content on the
line.

**Regex:** `r'^\s{6,8}([A-Z][A-Z0-9-]+)\.\s*$'`

Apply only to lines within the PROCEDURE DIVISION. Skip `MAIN-PROCEDURE`
either by allowlist or by starting the scan after the first rule paragraph
label is found.

**Expected Outcomes**
- A list of `(line_number, paragraph_name)` tuples in source order:
  `[(107, "STANDARD-ELIGIBILITY-RULE"), (123, "GRACE-PERIOD-RULE"),
    (137, "STATE-CARVE-OUT-RULE"), (146, "ORPHAN-RULE")]`

**Status** `[ ] pending`

---

## Sub-Task 2 — Paragraph body extraction

**Intent**
For each detected paragraph, collect all lines from the label line
(inclusive) to the line before the next paragraph label (exclusive), or
end of file. This is the paragraph body used for condition and action
extraction.

**Expected body ranges** (from actual source):
```
STANDARD-ELIGIBILITY-RULE : lines 107–122  (ends before GRACE-PERIOD-RULE at 123)
GRACE-PERIOD-RULE          : lines 123–136  (ends before STATE-CARVE-OUT-RULE at 137)
STATE-CARVE-OUT-RULE       : lines 137–145  (ends before ORPHAN-RULE at 146)
ORPHAN-RULE                : lines 146–152  (ends at EOF)
```

**Status** `[ ] pending`

---

## Sub-Task 3 — IF condition extraction

**Intent**
From each paragraph body, extract the raw text of the IF condition: every
line from the `IF` keyword line through (but not including) the first
action verb (`MOVE`, `COMPUTE`, `PERFORM`, `STOP`, etc.).

Strip leading whitespace but otherwise preserve the text verbatim — no
normalisation, no semantic parsing.

**Expected condition_text for each rule** (raw, multi-line joined):

| Rule | Condition (normalised for display) |
|---|---|
| STANDARD | `WS-POLICY-STATUS = 'A' AND WS-CLAIM-AMOUNT <= WS-COVERAGE-LIMIT` |
| GRACE | `WS-POLICY-STATUS = 'L' AND WS-DAYS-SINCE-LAPSE <= 30 AND WS-POLICY-TENURE-YEARS > 5` |
| CARVE-OUT | `WS-STATE-CODE = 'NY' AND WS-INCIDENT-DESCRIPTION = SPACES` |
| ORPHAN | `WS-FISCAL-QTR-END-FLAG = 'Y'` |

**Action words to use as condition-end sentinels:**
`{"MOVE", "COMPUTE", "PERFORM", "ADD", "SUBTRACT", "MULTIPLY",
 "DIVIDE", "INITIALIZE", "STOP", "GO", "END-IF"}`

**Status** `[ ] pending`

---

## Sub-Task 4 — Action text extraction

**Intent**
From each paragraph body, extract the raw text of all action statements
inside the IF block: lines from the first action verb through (but not
including) `END-IF`.

**Expected action_text for each rule:**

| Rule | Action lines |
|---|---|
| STANDARD | `MOVE 'Y' TO WS-PAYABLE` + `MOVE WS-CLAIM-AMOUNT TO WS-PAYOUT-AMOUNT` |
| GRACE | same MOVE pair |
| CARVE-OUT | same MOVE pair |
| ORPHAN | `COMPUTE WS-PAYOUT-AMOUNT = WS-PAYOUT-AMOUNT * 1.005` |

**Status** `[ ] pending`

---

## Sub-Task 5 — Comment block extraction

**Intent**
For each paragraph, scan backwards from the paragraph label line to collect
semantic comment lines immediately preceding it. Stop when a non-comment,
non-blank line is encountered.

**Semantic comment definition:**
A line qualifies as a semantic comment if it:
- starts with `*` in column 7 (COBOL comment indicator), AND
- is NOT a pure divider line matching `r'^\s*\*-+\s*$'`

The divider pattern `*---...---` appears before every paragraph but carries
no information — it must be excluded from `comment_text`.

**Expected results:**

| Paragraph | comment_text |
|---|---|
| STANDARD-ELIGIBILITY-RULE | `"Core eligibility check: policy must be active and the submitted amount must not exceed the coverage limit."` (from lines 109-110 inside the body — pre-label is divider only, so scan inside body too — see note below) |
| GRACE-PERIOD-RULE | Lines 118-121 joined |
| STATE-CARVE-OUT-RULE | Lines 133-135 joined |
| ORPHAN-RULE | `null` |

**Note on STANDARD-ELIGIBILITY-RULE:**
The semantic comment for STANDARD is *inside* the paragraph body (lines
109-110), not before the label. The pre-label material at line 106 is a
divider only. Two options:
  a) Scan pre-label lines backwards AND the first run of comment lines
     inside the body — collect all semantic comments within 5 lines of
     the label in either direction.
  b) Scan only the lines immediately *before* the label (pre-label window),
     then fall back to scanning the first comment lines inside the body.

Use option (b): check pre-label first; if only dividers are found, check
the first lines of the body for semantic comments (before the first `IF`).

**Status** `[ ] pending`

---

## Sub-Task 6 — JSON output

**Intent**
Write the four extracted rules to `pipeline/output/rules.json` as a JSON
array. Create the `pipeline/output/` directory if it does not exist.

**Schema per rule:**
```json
{
  "rule_id": "R1",
  "paragraph_name": "STANDARD-ELIGIBILITY-RULE",
  "source_line_start": 107,
  "source_line_end": 122,
  "condition_text": "...",
  "action_text": "...",
  "comment_text": "..." | null
}
```

**Status** `[ ] pending`

---

## Sub-Task 7 — Known Limitations appendix to PROJECT_OVERVIEW.md

**Intent**
Append a `## Known Limitations` section to `docs/PROJECT_OVERVIEW.md`
containing the scope-boundary text specified in the task.

**Status** `[ ] pending`

---

## Non-Goals

- Handling arbitrary production COBOL (explicitly out of scope per the
  Known Limitations text).
- Normalising or semantically interpreting conditions.
- Any LLM involvement.
- Handling nested IF blocks, PERFORM THRU, GO TO within a paragraph.
