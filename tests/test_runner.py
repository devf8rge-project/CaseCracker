"""Comprehensive test suite for CaseCracker testing engine, runner, and comparator."""

import os
import unittest

from casecracker.comparator import compare_outputs
from casecracker.edge_cases import generate_boundary_test_cases
from casecracker.execution import (
    extract_test_cases_from_problem,
    find_first_failing_test,
    run_all_tests,
    run_test_case,
)
from casecracker.models import TestCase, TestStatus
from casecracker.runner import (
    ExecutionLimits,
    check_syntax,
    execute_code,
    has_solve_function,
    is_sandbox_available,
)


class TestComparator(unittest.TestCase):
    def test_exact_match(self):
        res = compare_outputs("42", "42")
        self.assertTrue(res.matched)
        self.assertEqual(res.rule_used, "Exact match")

    def test_whitespace_normalization(self):
        # Trailing spaces and newlines
        res = compare_outputs("hello world\n", "hello world  \n\n")
        self.assertTrue(res.matched)
        self.assertIn("Whitespace-normalized", res.rule_used)

    def test_line_trimmed_match(self):
        res = compare_outputs("line 1  \nline 2", "  line 1\nline 2  ")
        self.assertTrue(res.matched)

    def test_structured_json_match(self):
        res = compare_outputs('{"a": 1, "b": 2}', '{"b": 2, "a": 1}')
        self.assertTrue(res.matched)
        self.assertIn("Structured/JSON", res.rule_used)

    def test_structured_list_match(self):
        res = compare_outputs("[1, 2, 3]", "[1,  2, 3]")
        self.assertTrue(res.matched)

    def test_numeric_float_tolerance_match(self):
        res = compare_outputs("3.14159265", "3.14159260", float_tolerance=1e-5)
        self.assertTrue(res.matched)
        self.assertIn("Numeric match", res.rule_used)

    def test_numeric_mismatch_exceeds_tolerance(self):
        res = compare_outputs("3.1415", "3.1500", float_tolerance=1e-5)
        self.assertFalse(res.matched)
        self.assertEqual(res.rule_used, "Mismatch")
        self.assertTrue(res.diff)

    def test_token_numeric_match(self):
        res = compare_outputs("1 2 3.00000001", "1 2 3", float_tolerance=1e-6)
        self.assertTrue(res.matched)

    def test_mismatch_generates_diff(self):
        res = compare_outputs("expected line\nsecond line", "wrong line\nsecond line")
        self.assertFalse(res.matched)
        self.assertIn("-expected line", res.diff)
        self.assertIn("+wrong line", res.diff)


class TestExecutionModes(unittest.TestCase):
    def test_stdin_stdout_script(self):
        code = "import sys\nprint(sum(int(x) for x in sys.stdin.read().split()))"
        self.assertFalse(has_solve_function(code))
        res = execute_code(code, stdin_input="10 20 30\n")
        self.assertTrue(res.success)
        self.assertEqual(res.stdout.strip(), "60")
        self.assertEqual(res.mode_used, "stdin_stdout")

    def test_solve_function_mode(self):
        code = "def solve(data):\n    return sum(int(x) for x in data.split())"
        self.assertTrue(has_solve_function(code))
        res = execute_code(code, stdin_input="5 15 25")
        self.assertTrue(res.success)
        self.assertEqual(res.stdout.strip(), "45")
        self.assertEqual(res.mode_used, "solve_function")

    def test_solve_with_structured_json_args(self):
        code = "def solve(nums):\n    return [x * 2 for x in nums]"
        res = execute_code(code, stdin_input="[1, 2, 3]")
        self.assertTrue(res.success)
        self.assertEqual(res.stdout.strip(), "[2, 4, 6]")


class TestSecurityAndReliability(unittest.TestCase):
    def test_sandbox_detected_on_macos(self):
        self.assertTrue(is_sandbox_available())

    def test_syntax_error_preflight(self):
        code = "def invalid_syntax(:"
        valid, msg, line = check_syntax(code)
        self.assertFalse(valid)
        self.assertIn("SyntaxError", msg)
        self.assertEqual(line, 1)

        res = execute_code(code)
        self.assertFalse(res.success)
        self.assertEqual(res.execution_time_ms, 0.0)

    def test_timeout_protection(self):
        code = "while True: pass"
        limits = ExecutionLimits(timeout_seconds=0.7)
        res = execute_code(code, limits=limits)
        self.assertFalse(res.success)
        self.assertTrue(res.timed_out)
        self.assertIn("Time Limit Exceeded", res.error_message)

    def test_network_isolation(self):
        code = """
import urllib.request
urllib.request.urlopen("https://example.com", timeout=1)
"""
        res = execute_code(code)
        self.assertFalse(res.success)
        self.assertTrue(
            "URLError" in res.stderr
            or "PermissionError" in res.stderr
            or "network communication is blocked" in (res.error_message or "")
        )

    def test_filesystem_write_isolation(self):
        forbidden_file = "/tmp/casecracker_test_unauth.txt"
        if os.path.exists(forbidden_file):
            try:
                os.remove(forbidden_file)
            except OSError:
                pass

        code = f"""
with open("{forbidden_file}", "w") as f:
    f.write("illegal")
"""
        res = execute_code(code)
        self.assertFalse(res.success)
        self.assertFalse(os.path.exists(forbidden_file))
        self.assertTrue(
            "PermissionError" in res.stderr
            or "unauthorized filesystem modification" in (res.error_message or "")
        )

    def test_runtime_exception_capture(self):
        code = "print(10 / 0)"
        res = execute_code(code)
        self.assertFalse(res.success)
        self.assertIn("ZeroDivisionError", res.error_message)
        self.assertEqual(res.error_line, 1)

    def test_output_truncation(self):
        code = "print('Z' * 100000)"
        limits = ExecutionLimits(max_output_bytes=1000)
        res = execute_code(code, limits=limits)
        self.assertTrue(res.success)
        self.assertIn("Output truncated", res.stdout)
        self.assertLessEqual(len(res.stdout), 2000)


class TestMultiTestCaseRunner(unittest.TestCase):
    def test_single_pass(self):
        code = "print(int(input()) * 2)"
        tc = TestCase(id="1", name="Test 1", input="5", expected_output="10")
        res = run_test_case(code, tc)
        self.assertEqual(res.status, TestStatus.PASS)
        self.assertEqual(res.actual_output.strip(), "10")

    def test_single_fail_assertion(self):
        code = "print(int(input()) + 1)"
        tc = TestCase(id="2", name="Test 2", input="5", expected_output="10")
        res = run_test_case(code, tc)
        self.assertEqual(res.status, TestStatus.FAIL)
        self.assertEqual(res.actual_output.strip(), "6")
        self.assertIsNotNone(res.diff)

    def test_single_error_crash(self):
        code = "val = int(input())\nprint(100 // val)"
        tc = TestCase(id="3", name="Test 3", input="0", expected_output="10")
        res = run_test_case(code, tc)
        self.assertEqual(res.status, TestStatus.ERROR)
        self.assertIn("ZeroDivisionError", res.error_message)

    def test_single_timeout(self):
        code = "while True: pass"
        tc = TestCase(id="4", name="Test 4", input="1", expected_output="1")
        limits = ExecutionLimits(timeout_seconds=0.6)
        res = run_test_case(code, tc, limits=limits)
        self.assertEqual(res.status, TestStatus.TIMEOUT)

    def test_independent_execution(self):
        # Test 1 crashes, Test 2 passes, Test 3 fails
        code = """
import sys
x = int(sys.stdin.read().strip())
if x == 0:
    raise ValueError("Zero not allowed")
elif x == 2:
    print(4)
else:
    print(999)
"""
        cases = [
            TestCase(id="c1", name="Crash case", input="0", expected_output="0"),
            TestCase(id="c2", name="Passing case", input="2", expected_output="4"),
            TestCase(id="c3", name="Failing case", input="3", expected_output="6"),
        ]
        suite = run_all_tests(code, cases)
        self.assertEqual(suite.total_tests, 3)
        self.assertEqual(suite.error_count, 1)
        self.assertEqual(suite.passed_count, 1)
        self.assertEqual(suite.failed_count, 1)

        self.assertEqual(suite.results[0].status, TestStatus.ERROR)
        self.assertEqual(suite.results[1].status, TestStatus.PASS)
        self.assertEqual(suite.results[2].status, TestStatus.FAIL)

    def test_find_first_failing_test(self):
        code = """
x = int(input())
if x == 1:
    print(1)
elif x == 2:
    print(99)  # wrong
else:
    print(3)
"""
        cases = [
            TestCase(id="t1", name="Pass 1", input="1", expected_output="1"),
            TestCase(id="t2", name="Fail 2", input="2", expected_output="2"),
            TestCase(id="t3", name="Pass 3", input="3", expected_output="3"),
        ]
        res = find_first_failing_test(code, cases)
        self.assertTrue(res.executed)
        self.assertFalse(res.passed)
        self.assertIsNotNone(res.first_failing_case)
        self.assertEqual(res.first_failing_case.test_case.name, "Fail 2")

    def test_extract_problem_examples(self):
        problem = """
Given an integer, double it.
Example 1:
Input: 4
Output: 8

Example 2:
Input: 10
Output: 20
"""
        cases = extract_test_cases_from_problem(problem)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0].input, "4")
        self.assertEqual(cases[0].expected_output, "8")
        self.assertEqual(cases[1].input, "10")
        self.assertEqual(cases[1].expected_output, "20")

    def test_boundary_edge_case_generation(self):
        cases = generate_boundary_test_cases("Constraints: 1 <= n <= 50000")
        self.assertGreaterEqual(len(cases), 5)
        names = [c.name for c in cases]
        self.assertTrue(any("Zero" in n for n in names))
        self.assertTrue(any("Negative" in n for n in names))
        self.assertTrue(any("Single" in n for n in names))
        self.assertTrue(any("Duplicate" in n for n in names))
        self.assertTrue(any("Empty" in n for n in names))
        # Verify generated cases are marked as generated
        self.assertTrue(all(c.is_generated for c in cases))


if __name__ == "__main__":
    unittest.main()
