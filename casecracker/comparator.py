"""Robust output comparison engine supporting whitespace normalization, JSON, and numeric tolerance."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from difflib import unified_diff
import json
import math
import re


@dataclass(frozen=True)
class ComparisonResult:
    matched: bool
    rule_used: str
    diff: str = ""
    details: str = ""


def _try_parse_structured(text: str) -> tuple[bool, object]:
    """Attempt to parse text as JSON or Python literal (dict, list, bool, etc.)."""
    s = text.strip()
    if not s:
        return False, None

    # Check if string resembles structured data
    if not ((s.startswith("{") and s.endswith("}")) or
            (s.startswith("[") and s.endswith("]")) or
            (s.startswith("(") and s.endswith(")"))):
        return False, None

    try:
        return True, json.loads(s)
    except Exception:
        pass

    try:
        val = ast.literal_eval(s)
        if isinstance(val, (dict, list, tuple, set)):
            return True, val
    except Exception:
        pass

    return False, None


def _compare_tokens(expected_str: str, actual_str: str, float_tol: float) -> tuple[bool, bool]:
    """Compare token by token. Returns (matched, is_numeric)."""
    e_tokens = expected_str.strip().split()
    a_tokens = actual_str.strip().split()

    if len(e_tokens) != len(a_tokens):
        return False, False

    is_numeric = False
    for e_tok, a_tok in zip(e_tokens, a_tokens):
        if e_tok == a_tok:
            continue
        try:
            e_f = float(e_tok)
            a_f = float(a_tok)
            if math.isclose(e_f, a_f, abs_tol=float_tol, rel_tol=float_tol):
                is_numeric = True
                continue
        except (ValueError, OverflowError):
            return False, False
        return False, False

    return True, is_numeric


def compare_outputs(
    expected: str,
    actual: str,
    float_tolerance: float = 1e-6,
) -> ComparisonResult:
    """Compare expected and actual outputs across multiple comparison strategies.

    Strategies applied in order:
    1. Exact Match: Direct string equality.
    2. Whitespace-Normalized Match: Stripping surrounding leading/trailing whitespace & newlines.
    3. Structured / JSON Match: Deep equality for JSON objects, dictionaries, or lists.
    4. Numeric Token Match: Numbers match within specified float tolerance.
    5. Line-Trimmed Match: Line-by-line match with per-line whitespace trimmed.
    6. Mismatch: Returns unified diff.
    """
    # Rule 1: Exact match
    if expected == actual:
        return ComparisonResult(
            matched=True,
            rule_used="Exact match",
            details="The actual output matches expected output character-for-character.",
        )

    exp_clean = expected.strip()
    act_clean = actual.strip()

    # Rule 2: Whitespace-normalized match (trailing newlines/spaces)
    if exp_clean == act_clean:
        return ComparisonResult(
            matched=True,
            rule_used="Whitespace-normalized match",
            details="Matched after normalizing surrounding and trailing whitespace.",
        )

    # Rule 3: Structured JSON / Python literal comparison
    e_is_struct, e_obj = _try_parse_structured(exp_clean)
    a_is_struct, a_obj = _try_parse_structured(act_clean)
    if e_is_struct and a_is_struct:
        if e_obj == a_obj:
            return ComparisonResult(
                matched=True,
                rule_used="Structured/JSON equality",
                details="Deep equivalence between JSON / structured objects verified.",
            )

    # Rule 4: Numeric comparison (single number)
    try:
        e_float = float(exp_clean)
        a_float = float(act_clean)
        if math.isclose(e_float, a_float, abs_tol=float_tolerance, rel_tol=float_tolerance):
            return ComparisonResult(
                matched=True,
                rule_used=f"Numeric match (tolerance: {float_tolerance:g})",
                details=f"Values {act_clean} and {exp_clean} match within tolerance {float_tolerance:g}.",
            )
    except (ValueError, OverflowError):
        pass

    # Rule 5: Token-level numeric / whitespace comparison
    tok_match, is_num = _compare_tokens(expected, actual, float_tolerance)
    if tok_match:
        rule_desc = f"Numeric token match (tolerance: {float_tolerance:g})" if is_num else "Token-level whitespace match"
        return ComparisonResult(
            matched=True,
            rule_used=rule_desc,
            details="All tokens matched after whitespace and numeric normalization.",
        )

    # Rule 6: Line-trimmed non-empty comparison
    exp_lines = [l.strip() for l in expected.splitlines() if l.strip()]
    act_lines = [l.strip() for l in actual.splitlines() if l.strip()]
    if exp_lines and exp_lines == act_lines:
        return ComparisonResult(
            matched=True,
            rule_used="Line-trimmed match",
            details="All non-empty lines match after trimming whitespace.",
        )

    # Mismatch: generate unified diff
    diff_lines = list(unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        fromfile="expected",
        tofile="actual",
        lineterm="",
    ))
    diff_text = "\n".join(diff_lines) if diff_lines else "- (expected output differs)\n+ (actual output)"

    return ComparisonResult(
        matched=False,
        rule_used="Mismatch",
        diff=diff_text,
        details="Output differs from expected output.",
    )
