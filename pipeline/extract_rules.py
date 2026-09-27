"""
pipeline/extract_rules.py — Stage 1: Rule Extraction

Reads legacy/claims_eligibility.cbl and writes pipeline/output/rules.json,
a structured table of every rule paragraph in the program.

Rule discovery is structural: any paragraph whose body contains exactly one
IF...END-IF block and no PERFORM of another paragraph is treated as a rule
candidate, regardless of its name. This means MAIN-PROCEDURE (which contains
only PERFORM statements and no IF block) is excluded automatically, and new
rule paragraphs are found without any name-based configuration.

SCOPE BOUNDARY — KNOWN LIMITATIONS:
    Structural discovery handles the common case automatically, but the scope
    boundary from before still holds. Within a candidate paragraph, the extractor
    still requires a single unnested IF block with no GO TO and no logic split
    across multiple paragraphs via PERFORM THRU. Real production COBOL frequently
    violates all of these assumptions. Generalizing to arbitrary legacy COBOL
    would require a proper COBOL grammar parser (e.g. building on an existing
    COBOL AST library) rather than paragraph-label and structure pattern matching.
    This is a known, deliberate scope boundary, not an oversight.
"""

import json
import pathlib
import re

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = pathlib.Path("legacy/claims_eligibility.cbl")
OUTPUT_FILE = pathlib.Path("pipeline/output/rules.json")

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

# Used in structural candidate detection to identify PERFORM statements.
PERFORM_RE = re.compile(r"^\s+PERFORM\b", re.IGNORECASE)


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
# Structural rule-candidate detection
# ---------------------------------------------------------------------------

def _is_rule_candidate(body_lines: list[str]) -> bool:
    """
    Return True if this paragraph looks like a rule paragraph structurally.

    Criteria (both must hold):
      1. Exactly one IF...END-IF block present (no nesting, no multiple IFs).
      2. No PERFORM of another paragraph name — which would mark this as an
         orchestrating paragraph like MAIN-PROCEDURE rather than a rule.

    Comment lines and blank lines are skipped in the count.
    """
    if_count    = 0
    endif_count = 0
    has_perform = False

    for line in body_lines:
        stripped = line.strip().upper()
        if not stripped or COMMENT_LINE_RE.match(line):
            continue
        first_word = stripped.split()[0]
        if first_word == "IF":
            if_count += 1
        elif first_word in ("END-IF", "END-IF."):
            endif_count += 1
        elif first_word == "PERFORM":
            has_perform = True

    return if_count == 1 and endif_count >= 1 and not has_perform


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_rules(source_path: pathlib.Path) -> list[dict]:
    all_lines = source_path.read_text().splitlines()

    # --- Pass 1: collect ALL paragraph labels within PROCEDURE DIVISION ---
    all_labels: list[tuple[int, str]] = []
    in_procedure = False
    for lineno, line in enumerate(all_lines, start=1):
        if "PROCEDURE DIVISION" in line.upper():
            in_procedure = True
        if not in_procedure:
            continue
        m = PARAGRAPH_LABEL_RE.match(line)
        if m:
            all_labels.append((lineno, m.group(1)))

    all_labels.sort(key=lambda t: t[0])

    # --- Pass 2: slice each paragraph body and filter to rule candidates ---
    label_positions: list[tuple[int, str]] = []

    for idx, (label_lineno, para_name) in enumerate(all_labels):
        if idx + 1 < len(all_labels):
            body_end = all_labels[idx + 1][0] - 1
        else:
            body_end = len(all_lines)
        body_lines = all_lines[label_lineno - 1 : body_end]
        if _is_rule_candidate(body_lines):
            label_positions.append((label_lineno, para_name))

    # --- Pass 3: extract each confirmed rule paragraph ---
    # Body boundaries are now computed relative to other RULE labels only,
    # so each body extends to the line before the next rule paragraph.
    rules: list[dict] = []
    for rule_idx, (label_lineno, para_name) in enumerate(label_positions):
        if rule_idx + 1 < len(label_positions):
            next_label_lineno = label_positions[rule_idx + 1][0]
            body_end = next_label_lineno - 1
        else:
            body_end = len(all_lines)

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
