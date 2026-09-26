"""
pipeline/recover_provenance.py — Stage 2: Provenance Recovery

Reads pipeline/output/rules.json and docs/change_requests/, and writes
pipeline/output/provenance.json — one entry per rule augmenting the
Stage 1 rule table with provenance status, matched document, matched
excerpt, and a plain-English confidence note.

LLM REASONING NOTICE:
    The provenance_status values, matched_document references, matched_excerpt
    selections, and confidence_notes in the output of this script were reasoned
    by an LLM (IBM Bob) during development and are hardcoded as static output.
    This script does NOT call any external API at runtime. Re-running it will
    reproduce the same judgments deterministically — it does not silently
    re-reason or regenerate results. If provenance judgments need to be revised
    (e.g. new documents are added to docs/change_requests/), an explicit new
    reasoning pass must be performed and the PROVENANCE_RESULTS table below
    must be updated manually with that new reasoning recorded.

    This design keeps the "deterministic core, LLM only at the edges, and
    auditable" contract of the pipeline: the judgment calls are made once,
    reviewed by a human, and then frozen into a reproducible artifact.

Provenance status vocabulary:
    "Documented"   — a real external document (change request, legal memo, etc.)
                     was found whose specific content justifies this rule's
                     numeric thresholds and business condition.
    "Self-Evident" — the rule's inline comment fully self-describes it; no
                     historical change event is expected to exist for this kind
                     of baseline business logic.
    "Unknown"      — no document in the available corpus explains this rule;
                     it has no inline comment and no external documentation.
"""

import json
import pathlib

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RULES_FILE      = pathlib.Path("pipeline/output/rules.json")
OUTPUT_FILE     = pathlib.Path("pipeline/output/provenance.json")

# ---------------------------------------------------------------------------
# Provenance judgments (reasoned by IBM Bob, reviewed and confirmed by human)
#
# Keyed by paragraph_name. Each entry contains the fields added by Stage 2.
# ---------------------------------------------------------------------------

PROVENANCE_RESULTS: dict[str, dict] = {
    "STANDARD-ELIGIBILITY-RULE": {
        "provenance_status": "Self-Evident",
        "matched_document":  None,
        "matched_excerpt":   None,
        "confidence_note": (
            "Baseline eligibility logic is fully described by its inline comment; "
            "no change-request or compliance document is expected to exist for the "
            "core business definition of a payable claim. Neither available document "
            "addresses active-policy eligibility or coverage-limit thresholds."
        ),
    },
    "GRACE-PERIOD-RULE": {
        "provenance_status": "Documented",
        "matched_document":  "CR-1994-0088.txt",
        "matched_excerpt": (
            "If policy lapsed within 30 days of claim date AND policyholder held "
            "continuous coverage > 5 years prior to lapse, treat claim as payable."
        ),
        "confidence_note": (
            "CR-1994-0088 specifies the exact 30-day window and 5-year tenure "
            "threshold that appear verbatim in the rule's condition; both numeric "
            "values match precisely, not just topically."
        ),
    },
    "STATE-CARVE-OUT-RULE": {
        "provenance_status": "Documented",
        "matched_document":  "legal-settlement-NY-2003.txt",
        "matched_excerpt": (
            "the company is required to process claims from New York-domiciled "
            "policyholders as payable even when the incident description field is "
            "not completed, provided all other material claim fields are present."
        ),
        "confidence_note": (
            "Legal memo specifies NY state and blank incident description as the "
            "exact trigger conditions; the COBOL comment directly names this "
            "document (see legal/settlement-NY-2003), and the memo explicitly "
            "restricts the rule to NY only."
        ),
    },
    "ORPHAN-RULE": {
        "provenance_status": "Unknown",
        "matched_document":  None,
        "matched_excerpt":   None,
        "confidence_note": (
            "No documentation found anywhere in the available records explaining "
            "the fiscal-quarter-end payout adjustment or the 1.005 multiplication "
            "factor; the rule has no inline comment, and neither available "
            "change-request document addresses end-of-quarter processing."
        ),
    },
}

# ---------------------------------------------------------------------------
# Main: merge Stage 1 rules with provenance judgments
# ---------------------------------------------------------------------------

def recover_provenance(
    rules_path: pathlib.Path,
    output_path: pathlib.Path,
) -> list[dict]:
    rules = json.loads(rules_path.read_text())

    augmented: list[dict] = []
    for rule in rules:
        name = rule["paragraph_name"]
        judgment = PROVENANCE_RESULTS.get(name)
        if judgment is None:
            raise ValueError(
                f"No provenance judgment defined for paragraph '{name}'. "
                "Add an entry to PROVENANCE_RESULTS before re-running."
            )
        augmented.append({**rule, **judgment})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(augmented, indent=2))
    return augmented


if __name__ == "__main__":
    results = recover_provenance(RULES_FILE, OUTPUT_FILE)
    print(f"Wrote {len(results)} provenance entries to {OUTPUT_FILE}")
    for r in results:
        print(f"  {r['rule_id']}  {r['paragraph_name']:<30}  {r['provenance_status']}")
