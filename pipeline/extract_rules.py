"""
pipeline/extract_rules.py — Stage 1: Rule Extraction

Reads legacy/claims_eligibility.cbl and writes pipeline/output/rules.json,
a structured table of every rule paragraph in the program.

SCOPE BOUNDARY — KNOWN LIMITATIONS:
    This extractor is intentionally scoped to clean, one-paragraph-per-rule
    COBOL where each rule is a single IF block with no nesting, no GO TO,
    and no logic split across multiple paragraphs via PERFORM THRU. Real
    production COBOL frequently violates all of these assumptions. This
    extractor demonstrates the pipeline's method on a controlled fixture;
    generalizing it to arbitrary legacy COBOL would require a proper COBOL
    grammar parser (e.g. building on an existing COBOL AST library) rather
    than paragraph-label pattern matching. This is a known, deliberate scope
    boundary, not an oversight.
"""

import json
import pathlib
import re

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = pathlib.Path("legacy/claims_eligibility.cbl")
OUTPUT_FILE = pathlib.Path("pipeline/output/rules.json")

# Explicit allowlist — only these paragraph names are treated as rule
# paragraphs. MAIN-PROCEDURE and any other structural paragraphs are ignored.
RULE_PARAGRAPH_NAMES = [
    "STANDARD-ELIGIBILITY-RULE",
    "GRACE-PERIOD-RULE",
    "STATE-CARVE-OUT-RULE",
    "ORPHAN-RULE",
]

# Pattern that identifies a paragraph label line in Area A.
# Matches 6-8 leading spaces, an all-caps identifier with hyphens, then "."
PARAGRAPH_LABEL_RE = re.compile(r"^\s{6,8}([A-Z][A-Z0-9-]+)\.\s*$")

# Line is a pure divider comment if it is a COBOL comment (*) whose
# non-asterisk content is nothing but hyphens and whitespace.
DIVIDER_RE = re.compile(r"^\s*\*-+\s*$")

# COBOL comment line (column-7 asterisk, any content).
COMMENT_LINE_RE = re.compile(r"^\s*\*")

# Action verbs that mark the start of the IF body (end of condition).
ACTION_VERBS = {
    "MOVE", "COMPUTE", "PERFORM", "ADD", "SUBTRACT",
    "MULTIPLY", "DIVIDE", "INITIALIZE", "STOP", "GO",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_semantic_comment(line: str) -> bool:
    """True if line is a COBOL comment that is NOT a pure divider."""
    return bool(COMMENT_LINE_RE.match(line)) and not bool(DIVIDER_RE.match(line))


def _strip_comment_marker(line: str) -> str:
    """Remove the leading '*' comment indicator and strip surrounding whitespace."""
    return re.sub(r"^\s*\*\s?", "", line).strip()


def _extract_condition(body_lines: list[str]) -> str:
    """Return the raw IF condition text (from IF keyword to first action verb)."""
    collecting = False
    parts: list[str] = []
    for line in body_lines:
        stripped = line.strip()
        if not collecting:
            if stripped.upper().startswith("IF ") or stripped.upper() == "IF":
                collecting = True
                # Take the part after the IF keyword
                parts.append(stripped[3:].strip() if stripped.upper().startswith("IF ") else "")
        else:
            first_word = stripped.split()[0].upper() if stripped.split() else ""
            if first_word in ACTION_VERBS or first_word == "END-IF":
                break
            if stripped and not COMMENT_LINE_RE.match(line):
                parts.append(stripped)
    return " ".join(p for p in parts if p).strip()


def _extract_action(body_lines: list[str]) -> str:
    """Return the raw action statements inside the IF block (before END-IF)."""
    collecting = False
    parts: list[str] = []
    for line in body_lines:
        stripped = line.strip()
        if not collecting:
            first_word = stripped.split()[0].upper() if stripped.split() else ""
            if first_word in ACTION_VERBS:
                collecting = True
                parts.append(stripped)
        else:
            if stripped.upper() == "END-IF." or stripped.upper() == "END-IF":
                break
            if stripped and not COMMENT_LINE_RE.match(line):
                parts.append(stripped)
    return " ".join(parts).strip()


def _extract_comment(all_lines: list[str], label_lineno: int, body_lines: list[str]) -> str | None:
    """
    Extract semantic comment text for a paragraph.

    Strategy (option b from the plan):
      1. Scan backwards from the label line for semantic comments (skip
         dividers, stop at non-comment non-blank).
      2. If nothing found pre-label, scan forward inside the body for
         comment lines before the first IF.
      3. If still nothing, return None.

    Line numbers are 1-based; all_lines is 0-indexed.
    """
    # --- Step 1: pre-label scan (backwards) ---
    pre_label_comments: list[str] = []
    idx = label_lineno - 2  # 0-based index of the line above the label
    while idx >= 0:
        line = all_lines[idx]
        if _is_semantic_comment(line):
            pre_label_comments.insert(0, _strip_comment_marker(line))
        elif DIVIDER_RE.match(line) or line.strip() == "":
            pass  # skip dividers and blanks, keep scanning
        else:
            break  # non-comment, non-blank, non-divider — stop
        idx -= 1

    if pre_label_comments:
        return " ".join(pre_label_comments)

    # --- Step 2: intra-body scan (before first IF) ---
    intra_comments: list[str] = []
    for line in body_lines:
        stripped = line.strip()
        if stripped.upper().startswith("IF ") or stripped.upper() == "IF":
            break
        if _is_semantic_comment(line):
            intra_comments.append(_strip_comment_marker(line))

    if intra_comments:
        return " ".join(intra_comments)

    return None


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_rules(source_path: pathlib.Path) -> list[dict]:
    all_lines = source_path.read_text().splitlines()

    # --- Pass 1: find label line numbers for all rule paragraphs ---
    label_positions: list[tuple[int, str]] = []  # (1-based lineno, name)
    for lineno, line in enumerate(all_lines, start=1):
        m = PARAGRAPH_LABEL_RE.match(line)
        if m and m.group(1) in RULE_PARAGRAPH_NAMES:
            label_positions.append((lineno, m.group(1)))

    # Sort by appearance order (should already be in order, but be explicit)
    label_positions.sort(key=lambda t: t[0])

    # --- Pass 2: extract each rule ---
    rules: list[dict] = []
    for rule_idx, (label_lineno, para_name) in enumerate(label_positions):
        # Body: from label line to line before the next label (or EOF)
        if rule_idx + 1 < len(label_positions):
            next_label_lineno = label_positions[rule_idx + 1][0]
            body_end = next_label_lineno - 1        # 1-based, inclusive
        else:
            body_end = len(all_lines)

        # 0-based slice for the body
        body_lines = all_lines[label_lineno - 1 : body_end]

        condition = _extract_condition(body_lines)
        action    = _extract_action(body_lines)
        comment   = _extract_comment(all_lines, label_lineno, body_lines)

        rules.append({
            "rule_id":          f"R{rule_idx + 1}",
            "paragraph_name":   para_name,
            "source_line_start": label_lineno,
            "source_line_end":   body_end,
            "condition_text":   condition,
            "action_text":      action,
            "comment_text":     comment,
        })

    return rules


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    rules = extract_rules(SOURCE_FILE)
    OUTPUT_FILE.write_text(json.dumps(rules, indent=2))
    print(f"Wrote {len(rules)} rules to {OUTPUT_FILE}")
