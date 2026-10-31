import json
import unittest
from unittest.mock import patch, MagicMock
from casecracker.ai_helper import make_llm


class AITransportTests(unittest.TestCase):
    def test_interactions_json_response_and_privacy(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'status': 'completed', 'steps': [
            {'type': 'thought', 'summary': 'ignored'},
            {'type': 'model_output', 'content': [{'type': 'text', 'text': '{"ready": true}'}]},
        ]}).encode()
        with patch('urllib.request.urlopen', return_value=response) as call:
            self.assertTrue(make_llm('test-key', 'gemini-3.1-flash-lite')('Return ready JSON')['ready'])
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertTrue(request.full_url.endswith('/v1beta/interactions'))
        self.assertFalse(body['store'])
        self.assertEqual(body['generation_config']['thinking_level'], 'low')
        self.assertNotIn('test-key', str(body))

    def test_incomplete_output_is_not_used(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"status":"incomplete","steps":[]}'
        with patch('urllib.request.urlopen', return_value=response):
            with self.assertRaises(ValueError):
                make_llm('test-key')('Return JSON')
