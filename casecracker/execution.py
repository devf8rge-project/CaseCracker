"""Test orchestration engine executing test cases independently through the secure sandbox."""

from __future__ import annotations

import re
import uuid

from casecracker.comparator import compare_outputs
from casecracker.models import (
    SearchResult,
    TestCase,
    TestResult,
    TestStatus,
    TestSuiteResult,
    TestSuggestion,
)
from casecracker.runner import (
    ExecutionLimits,
    check_syntax,
    execute_code,
    is_sandbox_available,
)


def extract_test_cases_from_problem(problem: str) -> list[TestCase]:
    """Extract sample test cases (input and expected output) from problem text."""
    if not problem:
        return []

    pattern = re.compile(
        r"(?:Example\s*(\d+)?:?\s*)?(?:Input|Sample Input|Example input)\s*:\s*\n?(.*?)\s*(?:Output|Sample Output|Expected output)\s*:\s*\n?(.*?)(?=(?:Example|\Z|Explanation|Constraints))",
        re.DOTALL | re.IGNORECASE,
    )
    matches = pattern.findall(problem)
    cases: list[TestCase] = []

    for idx, (ex_num, inp, out) in enumerate(matches, start=1):
        cleaned_in = inp.strip()
        cleaned_out = out.strip()
        if cleaned_in or cleaned_out:
            label = f"Example {ex_num}" if ex_num else f"Sample Case {idx}"
            cases.append(
                TestCase(
                    id=f"example_{idx}_{str(uuid.uuid4())[:4]}",
                    name=label,
                    input=cleaned_in,
                    expected_output=cleaned_out,
                    explanation="Extracted from problem statement.",
                    is_generated=False,
                )
            )

    return cases


def run_test_case(
    code: str,
    test_case: TestCase,
    limits: ExecutionLimits = ExecutionLimits(),
) -> TestResult:
    """Run a single test case independently in an isolated sandbox subprocess."""
    exec_res = execute_code(code, stdin_input=test_case.input, limits=limits)

    if not exec_res.success:
        if exec_res.timed_out:
            status = TestStatus.TIMEOUT
            error_msg = exec_res.error_message or f"Time Limit Exceeded (> {limits.timeout_seconds:.1f}s)"
        else:
            status = TestStatus.ERROR
            error_msg = exec_res.error_message or "Runtime exception"

        return TestResult(
            test_case=test_case,
            status=status,
            actual_output=exec_res.stdout,
            execution_time_ms=exec_res.execution_time_ms,
            stderr=exec_res.stderr,
            error_message=error_msg,
            error_traceback=exec_res.error_traceback,
            sandboxed=exec_res.sandboxed,
        )

    # Execution succeeded (exit code 0)
    actual_out = exec_res.stdout

    # If an expected output was provided, compare them
    if test_case.expected_output.strip():
        comp_res = compare_outputs(expected=test_case.expected_output, actual=actual_out)
        status = TestStatus.PASS if comp_res.matched else TestStatus.FAIL
        return TestResult(
            test_case=test_case,
            status=status,
            actual_output=actual_out,
            execution_time_ms=exec_res.execution_time_ms,
            stderr=exec_res.stderr,
            comparison_rule=comp_res.rule_used,
            diff=comp_res.diff if not comp_res.matched else None,
            error_message=None if comp_res.matched else "Output mismatch",
            sandboxed=exec_res.sandboxed,
        )

    # If no expected output was provided (unverified exploratory case)
    return TestResult(
        test_case=test_case,
        status=TestStatus.UNVERIFIED,
        actual_output=actual_out,
        execution_time_ms=exec_res.execution_time_ms,
        stderr=exec_res.stderr,
        comparison_rule="Unverified (no expected output provided)",
        diff=None,
        error_message=None,
        sandboxed=exec_res.sandboxed,
    )


def run_all_tests(
    code: str,
    test_cases: list[TestCase],
    limits: ExecutionLimits = ExecutionLimits(),
) -> TestSuiteResult:
    """Run all test cases independently, aggregating results even if individual tests crash or fail."""
    # 1. Pre-execution static syntax validation
    valid_syntax, syn_msg, syn_line = check_syntax(code)
    if not valid_syntax:
        return TestSuiteResult(
            results=[],
            total_tests=len(test_cases),
            syntax_error=syn_msg,
            syntax_error_line=syn_line,
            sandboxed=is_sandbox_available(),
        )

    results: list[TestResult] = []
    passed = failed = errors = timeouts = unverified = 0
    total_ms = 0.0

    for tc in test_cases:
        res = run_test_case(code, tc, limits=limits)
        results.append(res)
        total_ms += res.execution_time_ms

        if res.status == TestStatus.PASS:
            passed += 1
        elif res.status == TestStatus.FAIL:
            failed += 1
        elif res.status == TestStatus.ERROR:
            errors += 1
        elif res.status == TestStatus.TIMEOUT:
            timeouts += 1
        elif res.status == TestStatus.UNVERIFIED:
            unverified += 1

    return TestSuiteResult(
        results=results,
        total_tests=len(test_cases),
        passed_count=passed,
        failed_count=failed,
        error_count=errors,
        timeout_count=timeouts,
        unverified_count=unverified,
        total_duration_ms=total_ms,
        sandboxed=is_sandbox_available(),
    )


def find_first_failing_test(
    code: str,
    test_cases: list[TestCase],
    limits: ExecutionLimits = ExecutionLimits(),
) -> SearchResult:
    """Run test cases in sequence to identify the first failing or crashing test case."""
    valid_syntax, syn_msg, syn_line = check_syntax(code)
    if not valid_syntax:
        return SearchResult(
            executed=False,
            message=syn_msg or "Syntax error in solution code.",
            error=syn_msg,
            sandboxed=is_sandbox_available(),
            suite_result=TestSuiteResult(
                syntax_error=syn_msg,
                syntax_error_line=syn_line,
                sandboxed=is_sandbox_available(),
            ),
        )

    suite = run_all_tests(code, test_cases, limits=limits)

    first_failing: TestResult | None = None
    for res in suite.results:
        if res.status in (TestStatus.FAIL, TestStatus.ERROR, TestStatus.TIMEOUT):
            first_failing = res
            break

    if first_failing:
        status_label = {
            TestStatus.FAIL: "Output mismatch",
            TestStatus.ERROR: "Runtime crash",
            TestStatus.TIMEOUT: "Time Limit Exceeded",
        }.get(first_failing.status, "Failed")

        msg = f"🔴 Failing test found: {first_failing.test_case.name} ({status_label})"
        return SearchResult(
            executed=True,
            passed=False,
            message=msg,
            test_input=first_failing.test_case.input,
            expected_output=first_failing.test_case.expected_output,
            actual_output=first_failing.actual_output or first_failing.error_message,
            execution_time_ms=first_failing.execution_time_ms,
            error=first_failing.error_message,
            sandboxed=first_failing.sandboxed,
            first_failing_case=first_failing,
            suite_result=suite,
        )

    # All tests passed or unverified
    all_passed = suite.passed_count == suite.total_tests and suite.total_tests > 0
    msg = (
        f"🟢 All {suite.total_tests} test cases passed!"
        if all_passed
        else f"Completed {suite.total_tests} test case(s) ({suite.passed_count} passed, {suite.unverified_count} unverified)."
    )

    first_tc = test_cases[0] if test_cases else None
    return SearchResult(
        executed=True,
        passed=all_passed,
        message=msg,
        test_input=first_tc.input if first_tc else None,
        expected_output=first_tc.expected_output if first_tc else None,
        actual_output=suite.results[0].actual_output if suite.results else None,
        execution_time_ms=suite.total_duration_ms,
        sandboxed=suite.sandboxed,
        suite_result=suite,
    )


def find_failing_test(
    problem: str, code: str, suggestion: TestSuggestion
) -> SearchResult:
    """Backward-compatible entry point executing submitted code against suggestion or problem examples."""
    test_cases: list[TestCase] = []

    if suggestion.test_input is not None:
        test_cases.append(
            TestCase(
                id="custom_case",
                name="Custom Test Case",
                input=suggestion.test_input,
                expected_output=suggestion.expected_output or "",
                explanation=suggestion.message,
            )
        )
    else:
        test_cases = extract_test_cases_from_problem(problem)

    if not test_cases:
        return SearchResult(
            executed=False,
            sandboxed=is_sandbox_available(),
            message="No test cases available. Add custom test cases or include 'Input:' and 'Output:' in your problem statement.",
        )

    return find_first_failing_test(code, test_cases)
