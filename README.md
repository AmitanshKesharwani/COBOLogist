# COBOLogist

> **A risk-auditing engine for legacy modernization that identifies business rules that may be silently lost during migration — and provides the evidence needed to understand why they matter.**

## Overview

Modernizing legacy systems such as COBOL applications is not simply a code-translation problem.

A translated program may compile, pass conventional tests, and still silently remove an undocumented business rule that has been relied upon for years.

The **Legacy Provenance Engine** addresses this problem by analyzing legacy business rules, their historical usage, their documentation, and the behavior of the modernized implementation.

The system produces an auditable report that answers:

* **What business rules exist in the legacy system?**
* **Where did those rules come from?**
* **How often did they actually occur in production history?**
* **Does the modern implementation behave differently?**
* **Which legacy rule is responsible for the divergence?**

---

# The Problem

Legacy systems often contain business logic that is difficult to understand or trace back to its original purpose.

A rule may have been introduced because of:

* an old regulatory requirement
* a contractual exception
* a fraud-prevention measure
* a temporary business decision
* an edge case discovered years ago

Over time, the people who introduced these rules may leave the organization, while the original documentation becomes difficult to locate.

Traditional modernization tools primarily focus on whether the translated code works.

The Legacy Provenance Engine adds another layer:

> **Before trusting the modernization, understand which legacy rules actually matter and whether the new implementation preserves them.**

---

# How It Works

The project uses a **four-stage pipeline**.

```text
             ┌──────────────────────┐
             │    Legacy COBOL      │
             │       Source         │
             └──────────┬───────────┘
                        │
                        ▼
              ┌───────────────────┐
              │ 1. Rule Extraction│
              └─────────┬─────────┘
                        │
                        ▼
                 rules.json
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
   ┌───────────────────┐   ┌───────────────────┐
   │ 2. Provenance      │   │ 3. Historical     │
   │    Recovery        │   │    Mining         │
   └─────────┬─────────┘   └─────────┬─────────┘
             │                       │
             ▼                       ▼
      provenance.json       firing_frequency.json
             │                       │
             └──────────┬────────────┘
                        │
                        ▼
              ┌────────────────────┐
              │ 4. Divergence      │
              │    Verification    │
              └──────────┬─────────┘
                         │
                         ▼
                 final_report.json
```

---

# Pipeline Stages

## 1. Rule Extraction

The first stage performs deterministic analysis of the legacy COBOL source.

It identifies business-rule decision points and records information such as:

* Rule ID
* Condition
* Action
* Paragraph name
* Source file
* Source line range

The result is a machine-readable rule catalogue.

```text
legacy/claims_eligibility.cbl
              │
              ▼
      Rule Extraction
              │
              ▼
pipeline/output/rules.json
```

This stage is intentionally deterministic so that the extracted rule table is reproducible and auditable.

---

## 2. Provenance Recovery

The second stage attempts to determine **why each rule exists**.

The rule catalogue is matched against available historical documentation such as:

* change requests
* commit messages
* comments
* compliance documents
* historical notes

Rules are classified according to the available evidence:

* **Documented** — a written artifact clearly explains the rule.
* **Inferred** — there is a plausible connection to available documentation.
* **Unknown** — no supporting documentation was found.

LLM assistance can be used for fuzzy matching of historical text, while the supporting evidence remains available for human review.

```text
rules.json
    +
Documentation Corpus
    │
    ▼
Provenance Recovery
    │
    ▼
provenance.json
```

---

## 3. Golden Dataset Mining

The third stage uses historical transaction data to determine how frequently each rule actually occurred.

The system replays the historical dataset and calculates information such as:

* Number of times a rule fired
* Years in which it fired
* Outcomes associated with the rule
* First and last observed occurrence

This provides empirical evidence about the historical importance of a rule.

```text
Historical Transactions
          +
      Rule Table
          │
          ▼
 Golden Dataset Mining
          │
          ▼
firing_frequency.json
```

This stage is deterministic: frequencies and counts are computed directly from the available data.

---

## 4. Divergence Verification

The final stage compares the legacy implementation against the modernized implementation.

Both implementations process the same historical transaction set.

```text
Historical Data
      │
      ├───────────────┐
      ▼               ▼
 Legacy COBOL     Modern Python
      │               │
      └───────┬───────┘
              ▼
       Output Comparison
              │
              ▼
         Divergences
```

When a difference is detected, the system uses **rule ablation** to determine which legacy rule caused it.

For each rule, an ablated version of the COBOL program is created where that rule's action is suppressed.

If suppressing a particular rule causes the legacy output to match the modern output, that rule becomes the candidate cause of the divergence.

This provides a concrete attribution mechanism instead of simply reporting that two programs produced different results.

---

# Ablation Testing

Ablation is one of the key mechanisms of the project.

For example:

```text
Original Rule:

IF ORPHAN-RULE-CONDITION
    PERFORM SPECIAL-ACTION
END-IF
```

The ablated version becomes:

```text
IF ORPHAN-RULE-CONDITION
    CONTINUE
END-IF
```

Everything else remains unchanged.

The outputs can then be compared:

```text
Original COBOL
      │
      ├── Claim A → APPROVED
      └── Claim B → DENIED

Ablated COBOL
      │
      ├── Claim A → DENIED
      └── Claim B → DENIED
```

If the modern implementation also produces `DENIED` for Claim A, the ablation provides evidence that the suppressed rule explains the divergence.

---

# Deterministic vs LLM-Assisted Components

A core design principle is to keep safety-critical verification deterministic.

| Stage                 | Approach      | Purpose                                      |
| --------------------- | ------------- | -------------------------------------------- |
| Rule Extraction       | Deterministic | Extract rules reproducibly                   |
| Provenance Recovery   | LLM-assisted  | Match rules against historical documentation |
| Golden Dataset Mining | Deterministic | Calculate real historical frequencies        |
| Divergence Detection  | Deterministic | Perform exact output comparison              |
| Report Narration      | LLM-assisted  | Explain detected findings in plain English   |

The LLM is **not responsible for deciding whether two program outputs are equal**.

The actual comparison remains deterministic and auditable.

---

# Example Finding

A potential output could look like:

```text
Rule #4 diverges.
No documentation found.
Fired 12 times in 5 years.
All observed outcomes were approved.
```

This is more useful than simply reporting:

```text
Legacy != Modern
```

The report connects the technical divergence with historical evidence and provenance.

---

# Demo Scenario

The repository contains a small claims-eligibility demonstration based on a legacy COBOL program.

The fixture contains several business rules, including:

* Standard eligibility logic
* A grace-period rule
* A state-specific regulatory exception
* An orphaned rule with no obvious documentation

The demonstration introduces a modernization error where the orphaned rule's behavior is silently lost.

The pipeline detects the resulting behavioral difference and connects it to:

1. The affected rule
2. Its historical firing frequency
3. Its documentation/provenance status
4. The resulting divergence

This demonstrates the central purpose of the project: **finding business logic that can disappear during modernization without being obvious from normal testing.**

---

# Output

The final pipeline produces a consolidated report:

```text
output/
└── final_report.json
```

A report entry can contain information such as:

```json
{
  "rule_id": "R4",
  "provenance": "Unknown",
  "times_fired": 12,
  "distinct_years_fired": 5,
  "divergence_count": 1,
  "example_record": "...",
  "risk_narrative": "..."
}
```

The exact fields depend on the current pipeline implementation.

The report is designed to be consumed by:

* auditors
* modernization teams
* risk analysts
* compliance teams
* downstream reporting systems

---

# Repository Structure

```text
legacy-provenance-engine/
│
├── legacy/
│   ├── claims_eligibility.cbl
│   └── ablation/
│
├── modern/
│   └── claims_eligibility.py
│
├── history/
│   └── production_log_2019_2024.jsonl
│
├── docs/
│   ├── change_requests/
│   └── PROJECT_OVERVIEW.md
│
├── pipeline/
│   ├── generate_ablation_variants.py
│   ├── verify_divergence.py
│   └── output/
│
├── .bob/
│   ├── custom_modes.yaml
│   └── skills/
│
├── bob_sessions/
│
├── output/
│
└── AGENTS.md
```

---

# Execution Flow

The intended workflow is:

```text
1. Extract rules
        ↓
2. Recover provenance
        ↓
3. Mine historical usage
        ↓
4. Generate ablation variants
        ↓
5. Compile and execute variants
        ↓
6. Run original COBOL program
        ↓
7. Compare COBOL vs Python
        ↓
8. Attribute divergences
        ↓
9. Generate final_report.json
```

---

# Key Design Principles

### Deterministic

The rule extraction, historical analysis, and output comparison are designed to be reproducible.

### Auditable

Important findings can be traced back to source rules, historical records, and documentation evidence.

### Attribution-focused

The system does not stop at detecting a difference. It attempts to identify the specific legacy rule responsible.

### Evidence-driven

Historical production behavior is used to determine whether a rule actually occurred and how frequently.

### Human-reviewable

LLM-assisted steps are limited to areas where human review can validate the underlying evidence.

---

# Role of IBM Bob

IBM Bob was used in two ways during development.

### Development Partner

Bob's Plan, Agent, and Orchestrator modes were used to help:

* decompose the architecture
* develop pipeline stages
* generate supporting files
* debug implementation issues
* coordinate development tasks

Development session exports are stored in:

```text
bob_sessions/
```

### Pipeline Component

Bob's document-understanding capability is also used in provenance recovery to perform fuzzy semantic matching between extracted rules and historical documentation.

This is intentionally limited to provenance matching and report narration rather than deterministic divergence detection.

---

# Positioning

The Legacy Provenance Engine is designed as a **pre-flight risk layer for modernization**.

Existing modernization and code-analysis tools can help with:

* code translation
* compiler upgrades
* dependency analysis
* code explanation
* test generation
* behavioral testing

This project focuses on a different question:

> **Before or during modernization, which legacy business rules have historical evidence behind them, where did they come from, and did the modernization preserve them?**

It is therefore intended to complement existing modernization tooling rather than replace it.

---

# Current Status

The project is currently structured around a controlled demonstration fixture.

The planned implementation includes:

* [ ] Fixture COBOL program
* [ ] Historical transaction dataset
* [ ] Change-request documentation corpus
* [ ] Modernized implementation
* [ ] Rule extraction
* [ ] Provenance recovery
* [ ] Golden dataset mining
* [ ] Divergence verification
* [ ] Bob custom modes and skills
* [ ] End-to-end pipeline execution
* [ ] Final impact metrics
* [ ] Pitch deck
* [ ] Demo rehearsal

Impact metrics such as the number of extracted rules, undocumented rules, and detected divergences should be populated after the complete fixture pipeline is executed.

---

# Known Limitations

The current rule extractor is intentionally scoped to a controlled COBOL structure.

It assumes relatively clean, one-paragraph-per-rule code where a rule can be represented as a single `IF` block without complex control flow.

Real-world COBOL may contain:

* nested conditions
* `GO TO`
* rules distributed across multiple paragraphs
* `PERFORM THRU`
* complex control flow
* shared business logic

Supporting arbitrary production COBOL would require a more complete COBOL parser and AST-based analysis.

This limitation is deliberate for the current proof-of-concept.

---

# Why This Project Matters

A successful modernization is not simply:

```text
Old Code → New Code
```

It should also answer:

```text
Old Rule
   ↓
Why did it exist?
   ↓
Did it actually matter?
   ↓
Did the new system preserve it?
   ↓
If not, what caused the difference?
```

The Legacy Provenance Engine provides this missing evidence layer.

---


---

## One-Line Summary

**Legacy Provenance Engine is an evidence-driven auditing pipeline that extracts legacy business rules, recovers their provenance, measures their historical usage, and detects which rules are silently lost during modernization.**
