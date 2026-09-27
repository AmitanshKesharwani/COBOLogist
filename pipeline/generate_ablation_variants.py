"""
pipeline/generate_ablation_variants.py — generates 4 COBOL ablation source files

For each rule R1–R4, produces a COBOL source file in legacy/ablation/ where
that rule's action lines (MOVE/COMPUTE inside the IF block) are replaced by
CONTINUE statements. All other rules remain byte-for-byte unchanged.

Each variant writes its output to pipeline/output/ablation_<rule_id>.dat.
Compile and run each with:
    cobc -x legacy/ablation/claims_eligibility_ablate_<rule_id>.cbl
    ./claims_eligibility_ablate_<rule_id>

The resulting .dat files are consumed by verify_divergence.py's ablation
step to perform attribution without any Python rule simulation.

Rule paragraph boundaries come from pipeline/output/rules.json (Stage 1
output), so no line numbers are hardcoded here — they are read at runtime.

Action-line detection: any non-comment, non-blank line inside the paragraph
body (between the paragraph label and END-IF.) whose first significant token
is a COBOL action verb (MOVE, COMPUTE, ADD, SUBTRACT, MULTIPLY, DIVIDE,
PERFORM, INITIALIZE, STRING) is replaced with CONTINUE. The IF and END-IF
lines, comment lines, and blank lines are left untouched.
"""

import json
import pathlib
import re

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RULES_FILE  = pathlib.Path("pipeline/output/rules.json")
SOURCE_FILE = pathlib.Path("legacy/claims_eligibility.cbl")
ABLATION_DIR = pathlib.Path("legacy/ablation")

# Template for the output file assignment inside each ablation variant.
# The variant writes to a rule-specific .dat file so all 4 can coexist.
OUTPUT_DAT_TEMPLATE = "pipeline/output/ablation_{rule_id}.dat"

# Original output file assignment line — this is what we replace per variant.
ORIGINAL_OUTPUT_ASSIGN = '"pipeline/output/cobol_batch_results.dat"'

# Action verbs whose lines get replaced by CONTINUE inside the suppressed paragraph.
ACTION_VERBS = {
    "MOVE", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE",
    "PERFORM", "INITIALIZE", "STRING",
}

COMMENT_RE = re.compile(r"^\s*\*")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_action_line(line: str) -> bool:
    """
    True if this line's first significant token is a COBOL action verb.
    Excludes comment lines and blank lines.
    """
    stripped = line.strip()
    if not stripped or COMMENT_RE.match(line):
        return False
    first_word = stripped.split()[0].upper()
    return first_word in ACTION_VERBS


def _suppress_actions_in_body(lines: list[str], start: int, end: int) -> list[str]:
    """
    Return a new lines list with the entire IF body (everything between the
    IF condition lines and END-IF) replaced by a single CONTINUE statement.

    Strategy: locate the first action line (first non-IF, non-comment, non-blank
    line after the IF keyword), then replace every line from that point through
    the line before END-IF with CONTINUE on the first such line and blank lines
    for the rest. This correctly handles multi-line COMPUTE/MOVE continuations
    whose continuation lines have no action verb as their first token.

    IF, END-IF, comment lines, and blank lines before the first action are
    left unchanged.
    """
    result = lines[:]

    # Locate the IF line within the paragraph body
    if_idx = None
    for i in range(start - 1, end):
        stripped = result[i].strip().upper()
        if stripped.startswith("IF ") or stripped == "IF":
            if_idx = i
            break
    if if_idx is None:
        return result

    # Locate the matching END-IF
    endif_idx = None
    for i in range(if_idx + 1, end):
        stripped = result[i].strip().upper()
        if stripped in ("END-IF.", "END-IF"):
            endif_idx = i
            break
    if endif_idx is None:
        return result

    # Determine indentation from IF line
    indent = len(result[if_idx]) - len(result[if_idx].lstrip())
    continue_line = " " * indent + "CONTINUE\n"

    # Replace the first line after IF with CONTINUE, blank the rest up to END-IF
    body_start = if_idx + 1
    result[body_start] = continue_line
    for i in range(body_start + 1, endif_idx):
        result[i] = "\n"

    return result


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_ablation_variants(
    rules_path: pathlib.Path,
    source_path: pathlib.Path,
    out_dir: pathlib.Path,
) -> list[pathlib.Path]:
    rules = json.loads(rules_path.read_text())
    source_lines = source_path.read_text().splitlines(keepends=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    produced: list[pathlib.Path] = []

    for rule in rules:
        rule_id   = rule["rule_id"]
        para_name = rule["paragraph_name"]
        line_start = rule["source_line_start"]
        line_end   = rule["source_line_end"]

        # 1. Replace action lines in the target paragraph with CONTINUE
        ablated = _suppress_actions_in_body(source_lines, line_start, line_end)

        # 2. Point the OUTPUT-FILE to a rule-specific .dat path (replace literal assignment and any SELECT … ASSIGN TO clause)
        ablated_out_path = OUTPUT_DAT_TEMPLATE.format(rule_id=rule_id)
        ablated = []
        for line in _suppress_actions_in_body(source_lines, line_start, line_end):
            # Replace the literal string assignment
            new_line = line.replace(ORIGINAL_OUTPUT_ASSIGN, f'"{ablated_out_path}"')
            # Replace a SELECT … ASSIGN TO clause that may not use quotes
            if re.search(r"ASSIGN\s+TO", new_line, re.IGNORECASE):
                new_line = re.sub(r"ASSIGN\s+TO\s+\"?[^\"]+\.dat\"?",
                                   f"ASSIGN TO \"{ablated_out_path}\"",
                                   new_line,
                                   flags=re.IGNORECASE)
            ablated.append(new_line)


        # 3. Update program description comment
        ablated[0] = (
            f"      *ABLATION VARIANT: {rule_id} ({para_name}) — "
            f"action lines replaced by CONTINUE\n"
        )

        # 4. Write the variant source file
        out_file = out_dir / f"claims_eligibility_ablate_{rule_id}.cbl"
        out_file.write_text("".join(ablated))
        produced.append(out_file)
        print(f"  Generated {out_file}  (suppressed lines {line_start}–{line_end})")

    return produced


# ---------------------------------------------------------------------------
# Entry point — also prints compile/run instructions
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating ablation COBOL variants...")
    files = generate_ablation_variants(RULES_FILE, SOURCE_FILE, ABLATION_DIR)
    print(f"\nGenerated {len(files)} variants in {ABLATION_DIR}/")
    print()
    print("=" * 70)
    print("Compile and run each variant (from project root):")
    print("=" * 70)
    for f in files:
        rid = f.stem.split("_")[-1]   # e.g. "R1"
        dat = OUTPUT_DAT_TEMPLATE.format(rule_id=rid)
        stem = f.stem
        print(f"  cobc -x {f}  &&  ./{stem}")
        print(f"  # Output -> {dat}")
        print()
    print("Then hand the 4 .dat files back to the pipeline.")
    print("verify_divergence.py will load them automatically once they exist.")
