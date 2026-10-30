import os
import unittest
from casecracker.runner import execute_code, ExecutionLimits, is_sandbox_available
from casecracker.execution import find_failing_test, extract_test_cases_from_problem
from casecracker.models import TestSuggestion


class TestSecureRunner(unittest.TestCase):
    def test_sandbox_detected_on_macos(self):
        # On macOS, sandbox-exec should be detected
        self.assertTrue(is_sandbox_available())

    def test_valid_code_execution(self):
        code = "import sys\nprint(sum(int(x) for x in sys.stdin.read().split()))"
        res = execute_code(code, stdin_input="10 20 30\n")
        self.assertTrue(res.success)
        self.assertEqual(res.stdout.strip(), "60")
        self.assertFalse(res.timed_out)
        self.assertGreater(res.execution_time_ms, 0)

    def test_syntax_error_handling(self):
        code = "def broken(:"
        res = execute_code(code)
        self.assertFalse(res.success)
        self.assertIn("Syntax error", res.error_message)
        self.assertEqual(res.execution_time_ms, 0.0)

    def test_timeout_protection(self):
        code = "while True: pass"
        limits = ExecutionLimits(timeout_seconds=0.8)
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

    def test_filesystem_isolation(self):
        forbidden_file = "/tmp/casecracker_test_should_fail.txt"
        if os.path.exists(forbidden_file):
            try:
                os.remove(forbidden_file)
            except OSError:
                pass

        code = f"""
with open("{forbidden_file}", "w") as f:
    f.write("unauthorized")
"""
        res = execute_code(code)
        self.assertFalse(res.success)
        self.assertFalse(os.path.exists(forbidden_file))
        self.assertTrue(
            "PermissionError" in res.stderr
            or "unauthorized filesystem modification" in (res.error_message or "")
        )

    def test_runtime_exception(self):
        code = "print(10 / 0)"
        res = execute_code(code)
        self.assertFalse(res.success)
        self.assertIn("ZeroDivisionError", res.stderr)

    def test_output_truncation(self):
        code = "print('A' * 100000)"
        limits = ExecutionLimits(max_output_bytes=1000)
        res = execute_code(code, limits=limits)
        self.assertTrue(res.success)
        self.assertIn("Output truncated", res.stdout)
        self.assertLessEqual(len(res.stdout), 2000)


class TestExecutionIntegration(unittest.TestCase):
    def test_problem_examples_extraction(self):
        problem = """
Given an integer n, return its double.
Example 1:
Input: 4
Output: 8

Example 2:
Input: -3
Output: -6
"""
        cases = extract_test_cases_from_problem(problem)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0], ("4", "8"))
        self.assertEqual(cases[1], ("-3", "-6"))

    def test_find_failing_test_with_mismatch(self):
        problem = "Double the input."
        # Buggy code adding 1 instead of doubling
        code = "print(int(input()) + 1)"
        suggestion = TestSuggestion(
            connected=True,
            message="Test case",
            test_input="4",
            expected_output="8",
        )
        result = find_failing_test(problem, code, suggestion)
        self.assertTrue(result.executed)
        self.assertFalse(result.passed)
        self.assertEqual(result.actual_output, "5")
        self.assertEqual(result.expected_output, "8")
        self.assertIn("Failing test found", result.message)

    def test_find_failing_test_with_match(self):
        problem = "Double the input."
        # Correct code
        code = "print(int(input()) * 2)"
        suggestion = TestSuggestion(
            connected=True,
            message="Test case",
            test_input="4",
            expected_output="8",
        )
        result = find_failing_test(problem, code, suggestion)
        self.assertTrue(result.executed)
        self.assertTrue(result.passed)
        self.assertEqual(result.actual_output, "8")
        self.assertIn("Passed", result.message)

    def test_extracts_and_runs_problem_examples(self):
        problem = """
Input: 10
Output: 20
"""
        code = "print(int(input()) * 2)"
        suggestion = TestSuggestion(connected=False, message="Stub")
        result = find_failing_test(problem, code, suggestion)
        self.assertTrue(result.executed)
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
