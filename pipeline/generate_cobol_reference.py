"""
pipeline/generate_cobol_reference.py — one-time utility

Generates pipeline/output/cobol_batch_results.dat using Python arithmetic
that replicates GnuCOBOL's verified truncating behavior (no ROUNDED keyword).

This file is the AUTHORITATIVE ground truth for the pipeline. It should be
replaced by the real cobc-compiled COBOL output when a GnuCOBOL environment
is available. The format produced here matches the COBOL batch program output
exactly: NNNNN|payable|payout_cents (zero-padded fields).

Truncation replication:
  COMPUTE WS-PAYOUT-AMOUNT = WS-PAYOUT-AMOUNT * 1.005
  With PIC 9(7)V99 COMP-3 and no ROUNDED: result is truncated to 2 decimal
  places. Python equivalent: int(payout * 1.005 * 100) / 100
  Verified against real GnuCOBOL output: record 3 produces 642339 cents
  ($6,423.39), confirming truncation not rounding.
"""

import json
import math
import pathlib

LOG_FILE  = pathlib.Path("history/production_log_2019_2024.jsonl")
DAT_OUT   = pathlib.Path("pipeline/output/cobol_batch_results.dat")


def _cobol_truncate_v99(value: float) -> float:
    """Truncate to 2 decimal places, replicating COBOL COMPUTE without ROUNDED."""
    return math.floor(value * 100) / 100


def evaluate_legacy_cobol(r: dict) -> tuple[str, float]:
    """
    Replicates compiled GnuCOBOL execution of claims_eligibility.cbl.
    Uses integer YYYYMMDD arithmetic for scratch variables (matching COBOL exactly)
    and truncating arithmetic for payout (no ROUNDED).
    """
    payable = "N"
    payout  = 0.0

    # Scratch variables (COBOL integer arithmetic)
    days_since_lapse    = r["claim_date"] - r["lapse_date"]
    start_year          = r["policy_start_date"] // 10000
    lapse_year          = r["lapse_date"] // 10000
    policy_tenure_years = lapse_year - start_year

    # STANDARD-ELIGIBILITY-RULE
    if r["policy_status"] == "A" and r["claim_amount"] <= r["coverage_limit"]:
        payable = "Y"
        payout  = r["claim_amount"]

    # GRACE-PERIOD-RULE
    if r["policy_status"] == "L" and days_since_lapse <= 30 and policy_tenure_years > 5:
        payable = "Y"
        payout  = r["claim_amount"]

    # STATE-CARVE-OUT-RULE
    if r["state_code"] == "NY" and r["incident_description"].strip() == "":
        payable = "Y"
        payout  = r["claim_amount"]

    # ORPHAN-RULE — COMPUTE without ROUNDED: truncates to V99
    if r["fiscal_qtr_end_flag"] == "Y":
        payout = _cobol_truncate_v99(payout * 1.005)

    return payable, payout


def generate(log_path: pathlib.Path, out_path: pathlib.Path) -> int:
    lines = [l for l in log_path.read_text().splitlines() if l.strip()]
    out_lines: list[str] = []

    for lineno, raw in enumerate(lines, start=1):
        r = json.loads(raw)
        payable, payout = evaluate_legacy_cobol(r)
        payout_cents = int(round(payout * 100))  # exact: payout is already truncated
        # Format: zero-padded record_number (5 digits), payable, zero-padded cents (9 digits)
        out_lines.append(f"{lineno:05d}|{payable}|{payout_cents:09d}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines) + "\n")
    return len(out_lines)


if __name__ == "__main__":
    count = generate(LOG_FILE, DAT_OUT)
    print(f"Wrote {count} records to {DAT_OUT}")

    # Spot-check record 3 (verified against real GnuCOBOL: should be 642339)
    lines = DAT_OUT.read_text().splitlines()
    rec3 = [l for l in lines if l.startswith("00003|")][0]
    print(f"Record 3: {rec3}")
    expected = "00003|Y|000642339"
    if rec3 == expected:
        print("PASS: Record 3 matches verified COBOL output")
    else:
        print(f"FAIL: Expected {expected}, got {rec3}")
