import json
import time
import unittest
from unittest.mock import patch

from casecracker.checker import check_suite, shrink_failing_input, trace_execution_divergence
from casecracker.runner import trace_code
from casecracker.ai_helper import generate_verified_patch, guess_failing_case

REFERENCE = '''n = int(input())
values = list(map(int, input().split()))
assert n >= 1 and len(values) == n
total = 0
for value in values:
    total += value
print(total)
'''
STUDENT = REFERENCE.replace('total += value', 'total += max(value, 0)')
INPUT = '6\n8 -9 4 -2 7 0'


class ProofTests(unittest.TestCase):
    def test_output_without_expected_is_not_a_pass(self):
        from casecracker.execution import find_failing_test
        from casecracker.models import TestSuggestion
        result = find_failing_test('', 'print(1)', TestSuggestion(True, 'manual', test_input=''))
        self.assertTrue(result.executed)
        self.assertIsNone(result.passed)

    def test_shrink_and_real_outputs(self):
        start = time.monotonic()
        result = shrink_failing_input(STUDENT, REFERENCE, INPUT)
        self.assertTrue(result['is_failure'])
        self.assertLess(len(result['shrunk_failing_input']), len(INPUT))
        self.assertLessEqual(result['iterations'], 10)
        self.assertLess(time.monotonic() - start, 3.7)
        self.assertNotEqual(result['actual'], result['expected'])
        report = check_suite(STUDENT, REFERENCE, [result['shrunk_failing_input']])
        self.assertFalse(report['is_verified'])
        self.assertTrue(report['cases'][0]['valid'])

    def test_invalid_reference_does_not_verify_or_shrink(self):
        result = shrink_failing_input(STUDENT, 'raise ValueError()', INPUT)
        self.assertFalse(result['is_failure'])
        self.assertEqual(result['shrunk_failing_input'], INPUT)
        self.assertFalse(check_suite(STUDENT, REFERENCE, [])['is_verified'])

    def test_unsupported_format_retains_original(self):
        result = shrink_failing_input('print(0)', 'print(1)', '2 3\n1 2 3\n4 5 6')
        self.assertTrue(result['is_failure'])
        self.assertEqual(result['shrunk_failing_input'], result['original_failing_input'])

    def test_integer_and_string_reduction(self):
        scalar = shrink_failing_input('print(int(input())+1)', 'print(int(input()))', '999')
        self.assertEqual(scalar['shrunk_failing_input'], '0')
        string = shrink_failing_input('s=input(); print(len(s)+1)', 's=input(); print(len(s))', 'abcdef')
        self.assertEqual(len(string['shrunk_failing_input']), 1)

    def test_multiline_count_stays_consistent(self):
        result = shrink_failing_input('n=int(input()); a=[int(input()) for _ in range(n)]; print(0)',
                                      'n=int(input()); a=[int(input()) for _ in range(n)]; assert n>0; print(sum(a))', '3\n-4\n2\n1')
        self.assertTrue(result['is_failure'])
        lines = result['shrunk_failing_input'].splitlines()
        self.assertEqual(int(lines[0]), len(lines)-1)

    def test_trace_divergence_and_cap(self):
        result = trace_execution_divergence(STUDENT, REFERENCE, '1\n-1')
        self.assertTrue(result['student_steps'])
        self.assertIsNotNone(result['first_divergence'])
        self.assertIn('total', result['first_divergence']['differences'])
        for step in result['student_steps']:
            self.assertNotIn('__builtins__', step['locals'])
            json.dumps(step['locals'])
        capped = trace_code('x=0\nfor i in range(1000):\n    x+=i\nprint(x)')
        self.assertEqual(len(capped['steps']), 100)
        self.assertTrue(capped['truncated'])

    def test_trace_crash_and_timeout(self):
        crashed = trace_code('x=1\nprint(x/0)')
        self.assertEqual(crashed['error'], 'ZeroDivisionError')
        self.assertTrue(crashed['steps'])
        timed = trace_code('while True: pass', timeout_seconds=.15)
        self.assertTrue(timed['timed_out'])

    def test_solve_function_trace_and_normalized_comparison(self):
        reference = 'def solve(x):\n    total = x * 2\n    return total\n'
        student = reference.replace('x * 2', 'x + 1')
        report = check_suite(student, reference, ['4'])
        self.assertFalse(report['is_verified'])
        trace = trace_execution_divergence(student, reference, '4')
        self.assertTrue(any('x' in step['locals'] for step in trace['student_steps']))
        self.assertIsNotNone(trace['first_divergence'])
        normalized = check_suite('print("[1, 2]")', 'print("[1,2]")', [''])
        self.assertTrue(normalized['is_verified'])

    def test_patch_retries_on_real_failed_suite(self):
        # First proposal changes one line but remains wrong for negatives.
        wrong = STUDENT.replace('total += max(value, 0)', 'total += abs(value)')
        proposals = iter([wrong, REFERENCE])
        prompts = []
        def llm(prompt):
            prompts.append(prompt)
            return {'patched_code': next(proposals), 'explanation': 'Use the signed value on line 6.'}
        result = generate_verified_patch(STUDENT, REFERENCE, INPUT, {},
            lambda code: check_suite(code, REFERENCE, [INPUT, '1\n-1', '1\n0']), llm=llm)
        self.assertTrue(result['is_verified'])
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(result['passed_count'], 3)
        self.assertIn('previous_failure', prompts[1])
        self.assertIn('-    total += max(value, 0)', result['diff_text'])

    def test_bad_ai_never_claims_verification(self):
        llm = lambda prompt: {'patched_code': 'def broken(:', 'explanation': 'bad'}
        result = generate_verified_patch(STUDENT, REFERENCE, INPUT, {}, lambda code: self.fail('must not run invalid patch'), llm=llm)
        self.assertFalse(result['is_verified'])
        self.assertEqual(result['attempts'], 3)
        empty = generate_verified_patch('print(0)', 'print(1)', '', {},
            lambda code: {'is_verified': True, 'passed_count': 0, 'total_count': 0},
            llm=lambda prompt: {'patched_code': 'print(1)', 'explanation': 'Change zero to one.'})
        self.assertFalse(empty['is_verified'])

    def test_blind_prompt_contains_only_student_code(self):
        prompts = []
        def llm(prompt):
            prompts.append(prompt)
            return {'input': '1', 'expected_output': '1', 'actual_output': '0', 'explanation': 'A guess.'}
        result = guess_failing_case('print(0)', llm=llm)
        self.assertFalse(result['verified'])
        self.assertIn('print(0)', prompts[0])
        self.assertNotIn(REFERENCE, prompts[0])


if __name__ == '__main__':
    unittest.main()
