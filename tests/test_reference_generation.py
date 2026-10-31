import os
os.environ.setdefault('CASECRACKER_RUNNER_BACKEND', 'local')

import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from casecracker.ai_helper import generate_reference_solution
from casecracker.checker import validate_reference_samples
from casecracker.execution import extract_test_cases_from_problem
from casecracker.examples import DEMO_EXAMPLE


class ReferenceGenerationTests(unittest.TestCase):
    def test_sample_parser_skips_prose_input_description(self):
        samples = extract_test_cases_from_problem(DEMO_EXAMPLE[0])
        self.assertEqual([(t.input, t.expected_output) for t in samples], [('3\n-2 0 5', '3')])

    def test_independent_generation_and_invalid_response(self):
        prompts = []
        def provider(prompt):
            prompts.append(prompt)
            return {'reference_code': 'print(sum(map(int, input().split())))', 'explanation': 'Sum values.'}
        result = generate_reference_solution('Print the sum of integers on one line.', llm=provider)
        self.assertEqual(result['source'], 'ai_generated')
        self.assertNotIn('student_code', prompts[0])
        with self.assertRaises(ValueError):
            generate_reference_solution('', llm=provider)
        with self.assertRaises(ValueError):
            generate_reference_solution('Unclear task', llm=lambda _: {'reference_code': '', 'explanation': 'Missing output rules.'})
        with self.assertRaises(SyntaxError):
            generate_reference_solution('Sum values', llm=lambda _: {'reference_code': 'def !', 'explanation': 'Bad syntax'})

    def test_known_outputs_are_required_and_bad_code_cannot_pass(self):
        samples = [{'input': '2 3', 'expected_output': '5'}, {'input': '-2 0', 'expected_output': '-2'}]
        self.assertTrue(validate_reference_samples('print(sum(map(int, input().split())))', samples)['samples_passed'])
        self.assertFalse(validate_reference_samples('print(5)', samples)['samples_passed'])
        self.assertFalse(validate_reference_samples('raise RuntimeError("boom")', samples)['samples_passed'])
        with self.assertRaises(ValueError):
            validate_reference_samples('print(0)', [])

    def test_ui_applies_only_sample_checked_reference_and_blocks_stale(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        next(b for b in app.button if b.label == 'Load example').click().run()
        code = 'n = int(input())\nvalues = list(map(int, input().split()))\nassert n >= 1 and len(values) == n\nprint(sum(values))'
        with patch('casecracker.reference_ui._provider', return_value=lambda _: {'reference_code': code, 'explanation': 'Sum signed values.'}):
            next(b for b in app.button if b.label == 'Generate reference from problem').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['reference_code'], code)
        self.assertTrue(app.session_state['generated_reference']['report']['samples_passed'])
        # A bad replacement is never installed over a passing candidate.
        with patch('casecracker.reference_ui._provider', return_value=lambda _: {'reference_code': 'print(0)', 'explanation': 'Wrong.'}):
            next(b for b in app.button if b.label == 'Generate reference from problem').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['reference_code'], code)
        app.session_state['problem'] = 'A different task'
        app.run()
        next(b for b in app.button if 'Find failing test' in b.label).click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Generate the AI reference again' in e.value for e in app.error))
