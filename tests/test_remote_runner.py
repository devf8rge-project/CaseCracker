import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from casecracker.runner import execute_code, ExecutionLimits


class RemoteRunnerTests(unittest.TestCase):
    def test_oversized_code_is_rejected_before_host_parsing(self):
        from casecracker.runner import check_syntax
        with patch('ast.parse') as parse:
            valid, message, _ = check_syntax('x' * 200001)
        self.assertFalse(valid)
        self.assertIn('200 KB', message)
        parse.assert_not_called()

    def test_public_ui_blocks_unconfigured_execution(self):
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ, {'CASECRACKER_RUNNER_BACKEND': 'e2b', 'E2B_API_KEY': '', 'GEMINI_API_KEY': ''}):
            app = AppTest.from_file('app.py', default_timeout=30).run()
            self.assertFalse(app.exception)
            next(b for b in app.button if b.label == 'Load execution demo').click().run()
            next(b for b in app.button if 'Find failing test' in b.label).click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('No submitted code was executed' in e.value for e in app.error))
            self.assertNotIn('proof_bundle', app.session_state)

    def test_no_key_blocks_execution_without_local_fallback(self):
        with patch.dict(os.environ, {'CASECRACKER_RUNNER_BACKEND':'e2b', 'E2B_API_KEY':''}), patch('subprocess.Popen') as spawn:
            result = execute_code('print(42)')
        self.assertFalse(result.success)
        self.assertFalse(result.sandboxed)
        self.assertIn('No submitted code was executed', result.error_message)
        spawn.assert_not_called()

    def test_failure_cleans_up_and_never_leaks_key(self):
        sandbox = MagicMock()
        sandbox.commands.run.side_effect = RuntimeError('private-test-key-in-url')
        with patch.dict(os.environ, {'CASECRACKER_RUNNER_BACKEND':'e2b', 'E2B_API_KEY':'private-test-key'}), patch('e2b.Sandbox.create',return_value=sandbox) as create:
            result = execute_code('print(42)')
        self.assertFalse(result.success)
        self.assertNotIn('private-test-key', result.stderr)
        self.assertFalse(create.call_args.kwargs['allow_internet_access'])
        self.assertTrue(create.call_args.kwargs['secure'])
        sandbox.kill.assert_called_once()
        for call in sandbox.files.write.call_args_list:
            self.assertNotIn('private-test-key', call.args[1])

    def test_adapter_with_real_worker_and_both_execution_modes(self):
        # Fake only the provider transport. The uploaded worker and resource-limited
        # Python child really run; this is not a live E2B service check.
        with tempfile.TemporaryDirectory() as folder:
            sandbox = MagicMock()
            def write(path, content, **kwargs):
                if path.endswith('cc_worker.py'):
                    content = content.replace('/home/user/', folder + '/')
                Path(folder, Path(path).name).write_text(content)
            sandbox.files.write.side_effect = write
            def run(command, **kwargs):
                self.assertIs(type(kwargs['timeout']), int)
                self.assertTrue(str(kwargs['timeout'] * 1000).isdigit())
                proc = subprocess.run([sys.executable,'-I','-B',str(Path(folder,'cc_worker.py'))],capture_output=True,text=True,timeout=8)
                self.assertEqual(proc.returncode,0,proc.stderr)
                return SimpleNamespace(stdout=proc.stdout)
            sandbox.commands.run.side_effect = run
            with patch.dict(os.environ, {'CASECRACKER_RUNNER_BACKEND':'e2b', 'E2B_API_KEY':'private-test-key'}), patch('e2b.Sandbox.create', return_value=sandbox):
                plain = execute_code('import os; print(os.getenv("E2B_API_KEY", "absent"))')
                self.assertTrue(plain.success, plain.stderr)
                self.assertEqual(plain.stdout.strip(),'absent')
                solved = execute_code('def solve(xs):\n    return sum(xs)', '[1,2,3]')
                self.assertTrue(solved.success, solved.stderr)
                self.assertEqual(solved.stdout.strip(),'6')
                self.assertTrue(solved.sandboxed)
            self.assertEqual(sandbox.kill.call_count,2)

    def test_invalid_worker_payload_fails_closed(self):
        sandbox=MagicMock()
        sandbox.commands.run.return_value.stdout='not json'
        with patch.dict(os.environ, {'CASECRACKER_RUNNER_BACKEND':'e2b','E2B_API_KEY':'test'}), patch('e2b.Sandbox.create',return_value=sandbox):
            result=execute_code('print(42)')
        self.assertFalse(result.success)
        self.assertFalse(result.sandboxed)
        sandbox.kill.assert_called_once()
