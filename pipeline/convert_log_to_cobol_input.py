"""
pipeline/convert_log_to_cobol_input.py — Step 1 of COBOL batch upgrade

Converts history/production_log_2019_2024.jsonl to a pipe-delimited
LINE SEQUENTIAL file readable by GnuCOBOL's UNSTRING.

Output schema (one line per record):
  record_number|policy_status|policy_start_date|lapse_date|claim_date|
  claim_amount_cents|coverage_limit_cents|state_code|incident_description|
  fiscal_qtr_end_flag

Dollar amounts are encoded as INTEGER CENTS (round(x * 100)) — NOT decimal
text. This is required because MOVE of decimal text into a COBOL PIC 9(7)V99
field silently produces a 100x magnitude error. The only verified-correct
path is: encode cents, UNSTRING into PIC 9(9), then COMPUTE V99 = cents / 100.

round() is used rather than int() to avoid floating-point representation
errors (e.g. 6391.44 * 100 = 639143.9999... in raw float -> round -> 639144).
"""

import json
import pathlib

JSONL_IN  = pathlib.Path("history/production_log_2019_2024.jsonl")
DAT_OUT   = pathlib.Path("history/production_log_2019_2024.dat")


def convert(jsonl_path: pathlib.Path, dat_path: pathlib.Path) -> int:
    lines = [l for l in jsonl_path.read_text().splitlines() if l.strip()]
    out_lines: list[str] = []

    for record_number, raw in enumerate(lines, start=1):
        r = json.loads(raw)
        claim_cents   = round(r["claim_amount"]   * 100)
        coverage_cents = round(r["coverage_limit"] * 100)

        fields = [
            str(record_number),
            r["policy_status"],
            str(r["policy_start_date"]),
            str(r["lapse_date"]),
            str(r["claim_date"]),
            str(claim_cents),
            str(coverage_cents),
            r["state_code"],
            r["incident_description"],   # may be "" for NY carve-out records
            r["fiscal_qtr_end_flag"],
        ]
        out_lines.append("|".join(fields))

    dat_path.write_text("\n".join(out_lines) + "\n")
    return len(out_lines)


if __name__ == "__main__":
    count = convert(JSONL_IN, DAT_OUT)
    print(f"Wrote {count} records to {DAT_OUT}")
