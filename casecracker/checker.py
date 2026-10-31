"""Execution-grounded comparisons, bounded reduction, and trace alignment."""
from __future__ import annotations

from dataclasses import asdict
from difflib import SequenceMatcher
import math
import time

from casecracker.runner import ExecutionLimits, execute_code, trace_code


def compare_case(student_code, reference_code, test_input, *, timeout=1.0):
    limits = ExecutionLimits(timeout_seconds=max(.01, timeout))
    reference = execute_code(reference_code, test_input, limits)
    if not reference.success:
        return {"valid": False, "failed": False, "reason": "Reference rejected this input or could not finish.",
                "reference": asdict(reference), "student": None}
    student = execute_code(student_code, test_input, limits)
    return {"valid": True, "failed": not student.success or student.stdout.rstrip() != reference.stdout.rstrip(),
            "expected": reference.stdout.rstrip(), "actual": student.stdout.rstrip(),
            "error": student.stderr if not student.success else "",
            "sandboxed": reference.sandboxed and student.sandboxed,
            "reference": asdict(reference), "student": asdict(student)}


def check_suite(student_code, reference_code, test_inputs, *, timeout=1.0):
    """All cases must execute and match; an empty or invalid suite never verifies."""
    cases = []
    for text in test_inputs:
        result = compare_case(student_code, reference_code, text, timeout=timeout)
        cases.append({"input": text, **result})
    passed = sum(c["valid"] and not c["failed"] for c in cases)
    return {"is_verified": bool(cases) and passed == len(cases), "passed_count": passed,
            "total_count": len(cases), "sandboxed": bool(cases) and all(c.get("sandboxed", False) for c in cases),
            "cases": cases}


def _format(text):
    lines = text.strip().splitlines()
    if len(lines) >= 2 and len(lines[0].split()) == 1:
        try:
            n = int(lines[0])
            tokens = " ".join(lines[1:]).split()
            if n > 0 and n == len(tokens):
                multiline = len(lines[1:]) == n and all(len(line.split()) == 1 for line in lines[1:])
                return tokens, lambda xs: str(len(xs)) + "\n" + ("\n" if multiline else " ").join(xs)
        except ValueError:
            pass
    if len(lines) == 1 and len(lines[0].split()) == 1:
        token = lines[0]
        try:
            int(token)
            return [token], lambda xs: xs[0] if xs else ""
        except ValueError:
            return list(token), lambda xs: "".join(xs)
    # Arbitrary matrices, multiple test groups, and mixed formats are not guessed.
    return None


def _candidates(text):
    parsed = _format(text)
    if parsed is None:
        return
    tokens, encode = parsed
    size = len(tokens)
    # ddmin-style chunk deletion, large chunks first. Preserve N >= 1.
    chunk = max(1, math.ceil(size / 2))
    while size > 1:
        for start in range(0, size, chunk):
            smaller = tokens[:start] + tokens[start + chunk:]
            if smaller:
                yield encode(smaller)
        if chunk == 1:
            break
        chunk = max(1, chunk // 2)
    for index, token in enumerate(tokens):
        try:
            number = int(token)
        except ValueError:
            continue
        if abs(number) > 10**12:
            targets = [0, -1 if number < 0 else 1]
        else:
            targets = [0, -1 if number < 0 else 1, int(number / 2)]
        for target in dict.fromkeys(targets):
            if abs(target) < abs(number):
                values = tokens.copy()
                values[index] = str(target)
                yield encode(values)


def shrink_failing_input(student_code, reference_code, failing_input_str, *, max_iterations=10, timeout_seconds=3.0):
    """Best reduction found within a budget, not a global-minimality guarantee.

    A successful reference run is required for every accepted reduction. Domain
    constraints beyond the supported shape must be enforced by the reference.
    """
    start = time.monotonic()
    deadline = start + min(3.0, max(.01, timeout_seconds))
    original = failing_input_str
    result = {"original_failing_input": original, "shrunk_failing_input": original,
              "expected": None, "actual": None, "error": "", "iterations": 0,
              "status": "inconclusive", "is_failure": False, "sandboxed": False,
              "minimality": "Smallest found within the search budget; global minimality is not established."}
    def probe(text):
        remaining = deadline - time.monotonic()
        if remaining <= .04:
            return None
        return compare_case(student_code, reference_code, text, timeout=min(.45, remaining / 2))
    try:
        baseline = probe(original)
        if not baseline or not baseline["valid"] or not baseline["failed"]:
            result["status"] = "Original input could not be confirmed as a failure."
            return result
        best, current = original, baseline
        result.update(is_failure=True, expected=baseline["expected"], actual=baseline["actual"],
                      error=baseline["error"], sandboxed=baseline["sandboxed"])
        visited = {original}
        while result["iterations"] < min(10, max_iterations):
            accepted = False
            for candidate in _candidates(best) or ():
                if candidate in visited:
                    continue
                visited.add(candidate)
                if time.monotonic() >= deadline or result["iterations"] >= min(10, max_iterations):
                    break
                result["iterations"] += 1
                trial = probe(candidate)
                if trial and trial["valid"] and trial["failed"]:
                    # Preserve wrong-output versus runtime-error class, preventing
                    # a reduced malformed input from turning a mismatch into a crash.
                    if trial["student"]["success"] != baseline["student"]["success"]:
                        continue
                    best, current, accepted = candidate, trial, True
                    break
            if not accepted:
                break
        result.update(shrunk_failing_input=best, expected=current["expected"], actual=current["actual"],
                      error=current["error"], sandboxed=current["sandboxed"],
                      status="reduced" if best != original else "unchanged")
    except Exception:
        result["status"] = "Reduction unavailable; original input retained."
    result["elapsed_ms"] = round((time.monotonic() - start) * 1000)
    return result


def trace_execution_divergence(student_code, reference_code, test_input):
    student = trace_code(student_code, test_input)
    reference = trace_code(reference_code, test_input)
    rows, first = [], None
    # Align only matching source lines. Different algorithms cannot be compared
    # by instruction index without inventing a causal relationship.
    a, b = student.get("steps", []), reference.get("steps", [])
    matcher = SequenceMatcher(None, [s["code_line"].strip() for s in a],
                              [s["code_line"].strip() for s in b], autojunk=False)
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            left, right = a[block.a + offset], b[block.b + offset]
            shared = left["locals"].keys() & right["locals"].keys()
            changes = {key: {"student": left["locals"][key], "reference": right["locals"][key]}
                       for key in sorted(shared) if left["locals"][key] != right["locals"][key]}
            row = {"student_step": block.a + offset + 1, "reference_step": block.b + offset + 1,
                   "student_line": left["line_no"], "reference_line": right["line_no"],
                   "code_line": left["code_line"], "student_locals": left["locals"],
                   "reference_locals": right["locals"], "differences": changes}
            rows.append(row)
            if changes and first is None:
                first = row
    return {"student_steps": a, "reference_steps": b, "aligned_steps": rows,
            "first_divergence": first, "student_status": student, "reference_status": reference,
            "summary": ("First observed difference in shared variables at an aligned source line. "
                        "This is evidence of different state, not proof of the bug's cause." if first else
                        "No comparable variable divergence found. Inspect final recorded states and errors; "
                        "different algorithms, names, or the 100-step cap may prevent alignment."),
            "alignment": "Matching source lines in execution order; locals are recorded BEFORE the line executes."}
