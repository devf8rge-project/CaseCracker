"""Runner integration with secure local sandboxed execution."""

from __future__ import annotations

import re
from casecracker.models import SearchResult, TestSuggestion
from casecracker.runner import execute_code, is_sandbox_available


def extract_test_cases_from_problem(problem: str) -> list[tuple[str, str]]:
    """Extract sample test cases (input and expected output) from problem text."""
    if not problem:
        return []

    pattern = re.compile(
        r"(?:Input|Sample Input)\s*:\s*\n?(.*?)\s*(?:Output|Sample Output)\s*:\s*\n?(.*?)(?=(?:Example|\Z|Explanation|Constraints))",
        re.DOTALL | re.IGNORECASE,
    )
    matches = pattern.findall(problem)
    cases = []
    for inp, out in matches:
        cleaned_in = inp.strip()
        cleaned_out = out.strip()
        if cleaned_in or cleaned_out:
            cases.append((cleaned_in, cleaned_out))
    return cases


def find_failing_test(
    problem: str, code: str, suggestion: TestSuggestion
) -> SearchResult:
    """Execute submitted code securely against suggested or extracted test cases.

    Enforces macOS Seatbelt sandboxing, resource bounds, execution timeouts,
    and output limits.
    """
    sandbox_status = is_sandbox_available()

    # Priority 1: If an explicit test input is provided (via suggestion or custom input)
    if suggestion.test_input is not None:
        exec_res = execute_code(code, stdin_input=suggestion.test_input)

        if not exec_res.success:
            err_detail = exec_res.error_message or (exec_res.stderr.strip() if exec_res.stderr else "Execution failed")
            return SearchResult(
                executed=True,
                passed=False,
                message=f"🔴 Test execution failed: {err_detail}",
                test_input=suggestion.test_input,
                expected_output=suggestion.expected_output,
                actual_output=exec_res.stdout or exec_res.stderr or f"[Process exited with code {exec_res.exit_code}]",
                execution_time_ms=exec_res.execution_time_ms,
                error=exec_res.error_message or exec_res.stderr,
                sandboxed=exec_res.sandboxed,
            )

        actual = exec_res.stdout.rstrip()
        expected = (suggestion.expected_output or "").rstrip()

        if suggestion.expected_output is not None:
            if actual == expected:
                return SearchResult(
                    executed=True,
                    passed=True,
                    message="🟢 Passed! The solution produced the exact expected output.",
                    test_input=suggestion.test_input,
                    expected_output=suggestion.expected_output,
                    actual_output=actual,
                    execution_time_ms=exec_res.execution_time_ms,
                    sandboxed=exec_res.sandboxed,
                )
            else:
                return SearchResult(
                    executed=True,
                    passed=False,
                    message="🔴 Failing test found! The actual output does not match expected output.",
                    test_input=suggestion.test_input,
                    expected_output=suggestion.expected_output,
                    actual_output=actual,
                    execution_time_ms=exec_res.execution_time_ms,
                    sandboxed=exec_res.sandboxed,
                )
        else:
            return SearchResult(
                executed=True,
                passed=True,
                message="⚡ Executed successfully in secure sandbox. Output recorded.",
                test_input=suggestion.test_input,
                expected_output=None,
                actual_output=actual,
                execution_time_ms=exec_res.execution_time_ms,
                sandboxed=exec_res.sandboxed,
            )

    # Priority 2: Try extracting sample test cases from the problem statement
    examples = extract_test_cases_from_problem(problem)
    if examples:
        for idx, (test_in, expected_out) in enumerate(examples, start=1):
            exec_res = execute_code(code, stdin_input=test_in)
            actual = exec_res.stdout.rstrip()
            expected = expected_out.rstrip()

            if not exec_res.success:
                err_detail = exec_res.error_message or (exec_res.stderr.strip() if exec_res.stderr else "Runtime error")
                return SearchResult(
                    executed=True,
                    passed=False,
                    message=f"🔴 Failing test found on problem Example {idx}: {err_detail}",
                    test_input=test_in,
                    expected_output=expected_out,
                    actual_output=exec_res.stdout or exec_res.stderr,
                    execution_time_ms=exec_res.execution_time_ms,
                    error=exec_res.error_message or exec_res.stderr,
                    sandboxed=exec_res.sandboxed,
                )

            if actual != expected:
                return SearchResult(
                    executed=True,
                    passed=False,
                    message=f"🔴 Failing test found on problem Example {idx}! Output mismatch.",
                    test_input=test_in,
                    expected_output=expected_out,
                    actual_output=actual,
                    execution_time_ms=exec_res.execution_time_ms,
                    sandboxed=exec_res.sandboxed,
                )

        # If all extracted examples passed
        first_in, first_out = examples[0]
        return SearchResult(
            executed=True,
            passed=True,
            message=f"🟢 Passed all {len(examples)} sample test case(s) found in the problem description!",
            test_input=first_in,
            expected_output=first_out,
            actual_output=first_out,
            sandboxed=sandbox_status,
        )

    # Priority 3: No test input provided and no examples in problem
    return SearchResult(
        executed=False,
        sandboxed=sandbox_status,
        message="The secure Python sandbox runner is connected and active. "
        "Enter a test case or include 'Input:' and 'Output:' in your problem statement to execute tests.",
    )
