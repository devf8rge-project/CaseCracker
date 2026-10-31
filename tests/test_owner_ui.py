import os
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class OwnerUITests(unittest.TestCase):
    def test_public_workspace_has_no_connection_controls(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(any(e.label == 'Service connections & setup' for e in app.expander))
        self.assertFalse(any(b.label == 'Check service connections' for b in app.button))

    def test_owner_tools_closed_without_password(self):
        with patch.dict(os.environ, {'CASECRACKER_OWNER_PASSWORD': ''}):
            app = AppTest.from_file('app.py', default_timeout=30)
            app.query_params['view'] = 'owner'
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(any(b.label == 'Check service connections' for b in app.button))
            self.assertTrue(app.info)

    def test_login_logout_and_secret_rotation(self):
        with patch.dict(os.environ, {'CASECRACKER_OWNER_PASSWORD': 'test-owner-password-12345'}):
            app = AppTest.from_file('app.py', default_timeout=30)
            app.query_params['view'] = 'owner'
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(any(b.label == 'Check service connections' for b in app.button))
            app.text_input[0].input('wrong password')
            next(b for b in app.button if b.label == 'Sign in').click().run()
            self.assertTrue(app.error)
            self.assertFalse(any(b.label == 'Check service connections' for b in app.button))
            app.text_input[0].input('test-owner-password-12345')
            next(b for b in app.button if b.label == 'Sign in').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any(b.label == 'Check service connections' for b in app.button))
            self.assertNotIn('owner_password_input', app.session_state)
            next(b for b in app.button if b.label == 'Sign out').click().run()
            self.assertFalse(any(b.label == 'Check service connections' for b in app.button))
            app.text_input[0].input('test-owner-password-12345')
            next(b for b in app.button if b.label == 'Sign in').click().run()
            os.environ['CASECRACKER_OWNER_PASSWORD'] = 'a-different-owner-password'
            app.run()
            self.assertFalse(any(b.label == 'Check service connections' for b in app.button))
