"""
Stage 3 — zero LLM involvement, pure deterministic computation. Every rule's
condition is evaluated directly against logged data; there is no judgment call
in this stage.

Reads pipeline/output/provenance.json and history/production_log_2019_2024.jsonl,
evaluates each rule's boolean condition against every historical record, and writes
pipeline/output/firing_frequency.json — one entry per rule augmenting the Stage 2
provenance table with empirical firing evidence.

Rules are evaluated independently and non-exclusively: a single record can fire
multiple rules simultaneously.  No early-exit or mutual-exclusion logic is applied.

Date arithmetic intentionally replicates the COBOL:
  WS-DAYS-SINCE-LAPSE     = WS-CLAIM-DATE - WS-LAPSE-DATE   (raw YYYYMMDD integers)
  WS-POLICY-TENURE-YEARS  = (lapse_date // 10000) - (policy_start_date // 10000)
"""

import json
import pathlib

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROVENANCE_FILE = pathlib.Path("pipeline/output/provenance.json")
LOG_FILE        = pathlib.Path("history/production_log_2019_2024.jsonl")
OUTPUT_FILE     = pathlib.Path("pipeline/output/firing_frequency.json")


# ---------------------------------------------------------------------------
# Sub-task 1 — I/O helpers
# ---------------------------------------------------------------------------

def load_provenance(path: pathlib.Path) -> list[dict]:
    """Load Stage 2 provenance entries from JSON."""
    return json.loads(path.read_text())


def load_log(path: pathlib.Path) -> list[tuple[int, dict]]:
    """
    Load JSONL transaction log.

    Returns a list of (1-based line number, record dict) tuples.
    Blank/empty lines are skipped without error.
    """
    records: list[tuple[int, dict]] = []
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        stripped = raw.strip()
        if stripped:
            records.append((lineno, json.loads(stripped)))
    return records


# ---------------------------------------------------------------------------
# Sub-task 2 — Rule condition evaluators
# ---------------------------------------------------------------------------

def _eval_standard(r: dict) -> bool:
    """STANDARD-ELIGIBILITY-RULE: active policy, amount within coverage limit."""
    return r["policy_status"] == "A" and r["claim_amount"] <= r["coverage_limit"]


def _eval_grace_period(r: dict) -> bool:
    """
    GRACE-PERIOD-RULE: lapsed policy, claim within 30 raw-integer days of lapse,
    tenure > 5 years.  Uses COBOL integer arithmetic exactly.
    """
    if r["policy_status"] != "L":
        return False
    days_since_lapse   = r["claim_date"] - r["lapse_date"]
    policy_tenure_years = r["lapse_date"] // 10000 - r["policy_start_date"] // 10000
    return days_since_lapse <= 30 and policy_tenure_years > 5


def _eval_state_carve_out(r: dict) -> bool:
    """STATE-CARVE-OUT-RULE: NY policyholder with blank incident description."""
    return r["state_code"] == "NY" and r["incident_description"].strip() == ""


def _eval_orphan(r: dict) -> bool:
    """ORPHAN-RULE: claim filed on a fiscal quarter-end date."""
    return r["fiscal_qtr_end_flag"] == "Y"


# Map paragraph name → evaluator function
_EVALUATORS: dict[str, object] = {
    "STANDARD-ELIGIBILITY-RULE": _eval_standard,
    "GRACE-PERIOD-RULE":         _eval_grace_period,
    "STATE-CARVE-OUT-RULE":      _eval_state_carve_out,
    "ORPHAN-RULE":               _eval_orphan,
}


# ---------------------------------------------------------------------------
# Sub-task 3 — Firing frequency computation
# ---------------------------------------------------------------------------

def compute_firing_stats(
    rule: dict,
    log_records: list[tuple[int, dict]],
) -> dict:
    """
    Evaluate rule against all log records and return firing statistics.

    Returns a dict with:
      times_fired          — count of records where condition is true
      distinct_years_fired — count of distinct calendar years (claim_date // 10000)
      first_fired          — lowest claim_date among firing records, or null
      last_fired           — highest claim_date among firing records, or null
      sample_record_lines  — up to 3 first-in-file-order 1-based line numbers
    """
    para_name = rule["paragraph_name"]
    evaluator = _EVALUATORS[para_name]

    fired_lines: list[int] = []
    fired_dates: list[int] = []

    for lineno, record in log_records:
        if evaluator(record):
            fired_lines.append(lineno)
            fired_dates.append(record["claim_date"])

    times_fired = len(fired_lines)

    return {
        "times_fired":          times_fired,
        "distinct_years_fired": len({d // 10000 for d in fired_dates}),
        "first_fired":          min(fired_dates) if fired_dates else None,
        "last_fired":           max(fired_dates) if fired_dates else None,
        "sample_record_lines":  fired_lines[:3],
    }


# ---------------------------------------------------------------------------
# Sub-task 4 — JSON output
# ---------------------------------------------------------------------------

def mine_golden_dataset(
    provenance_path: pathlib.Path,
    log_path: pathlib.Path,
    output_path: pathlib.Path,
) -> list[dict]:
    """Run Stage 3: compute firing frequencies and write firing_frequency.json."""
    provenance_entries = load_provenance(provenance_path)
    log_records        = load_log(log_path)

    augmented: list[dict] = []
    for rule in provenance_entries:
        stats = compute_firing_stats(rule, log_records)
        augmented.append({**rule, **stats})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(augmented, indent=2))
    return augmented


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = mine_golden_dataset(PROVENANCE_FILE, LOG_FILE, OUTPUT_FILE)

    print(f"Wrote {len(results)} entries to {OUTPUT_FILE}\n")
    print(f"{'rule_id':<6}  {'paragraph_name':<30}  {'times_fired':>11}  {'distinct_years':>14}")
    print("-" * 70)
    for r in results:
        print(
            f"{r['rule_id']:<6}  {r['paragraph_name']:<30}  "
            f"{r['times_fired']:>11}  {r['distinct_years_fired']:>14}"
        )
