import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class ProofUITests(unittest.TestCase):
    def test_reference_demo_shrink_trace_and_verified_patch(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        self.assertFalse(app.exception)
        next(b for b in app.button if b.label == 'Load execution demo').click().run()
        next(b for b in app.button if b.label == 'Find failing test →').click().run()
        self.assertFalse(app.exception)
        bundle = app.session_state['proof_bundle']
        self.assertTrue(bundle['shrink']['is_failure'])
        self.assertIsNotNone(bundle['trace']['first_divergence'])
        self.assertGreater(len(app.dataframe), 0)
        def fake_llm(prompt):
            return {'patched_code': bundle['reference'], 'explanation': 'Sum the signed value on line 6.'}
        with patch('casecracker.proof_ui._provider', return_value=fake_llm):
            next(b for b in app.button if b.label == 'Generate and verify a one-line patch').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state['verified_patch']['is_verified'])
        self.assertTrue(any('100%' in x.value for x in app.success))
        app.radio[0].set_value('Light').run()
        self.assertFalse(app.exception)
        # Changed code invalidates the patch action, but retains labeled evidence.
        app.session_state['code'] = 'print(0)'
        app.run()
        self.assertTrue(next(b for b in app.button if b.label == 'Generate and verify a one-line patch').disabled)

    def test_missing_llm_and_invalid_suite_are_graceful(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        next(b for b in app.button if b.label == 'Load execution demo').click().run()
        next(t for t in app.text_area if t.label == 'Regression inputs (JSON array of stdin strings)').input('{bad').run()
        next(b for b in app.button if b.label == 'Find failing test →').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)

        next(b for b in app.button if b.label == 'Load execution demo').click().run()
        next(b for b in app.button if b.label == 'Find failing test →').click().run()
        with patch('casecracker.proof_ui._provider', side_effect=ValueError('AI is not configured.')):
            next(b for b in app.button if b.label == 'Generate and verify a one-line patch').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state['verified_patch']['is_verified'])
