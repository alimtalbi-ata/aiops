"""Fail-closed provider completion metadata; all responses are synthetic mocks."""
import importlib.util
import json
import pathlib
import sys
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
spec = importlib.util.spec_from_file_location('completion_gate', ROOT / 'app/shared/provider_completion.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
ai_spec = importlib.util.spec_from_file_location('aiops_provider_gate_v27', ROOT / 'app/intelligence/main.py')
ai = importlib.util.module_from_spec(ai_spec)
ai_spec.loader.exec_module(ai)


def response(content='{"ok":true}', **overrides):
    choice = {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': content}}
    choice.update(overrides)
    return {'choices': [choice]}


def mock_response(payload):
    result = Mock()
    result.raise_for_status.return_value = None
    result.json.return_value = payload
    return result


def analyst_json():
    return {
        'contract_version': '2.0', 'classification': 'storage-path',
        'severity': 'P1', 'severity_rationale': 'synthetic observation',
        'hypotheses': [{'id': 'H1', 'statement': 'synthetic path degradation',
                        'confidence': .9, 'supporting_evidence_ids': ['E1']}],
        'confidence': .9, 'confidence_basis': 'synthetic fixture'
    }


def critic_json(extra=False):
    claim = {'claim': 'Unproven impact', 'supported': False,
             'supporting_evidence_ids': [], 'contradicting_evidence_ids': []}
    if extra:
        claim['assumptions'] = ['unknown']
    return {'validated': False, 'issues': [], 'claim_checks': [claim],
            'diagnostic_confidence': .3, 'final_recommendation': 'HUMAN_APPROVAL',
            'unsafe_actions': ['No live changes'], 'limitations': ['Unknown impact']}


class ProviderCompletionTests(unittest.TestCase):
    def test_valid_assistant_completion(self):
        self.assertEqual(gate.extract_complete_completion(response()), '{"ok":true}')

    def test_rejects_ambiguous_or_error_envelopes(self):
        for payload in (None, {}, {'error': 'failed'}, {'choices': []},
                        {'choices': [response()['choices'][0]] * 2}, {'choices': 'bad'}):
            with self.subTest(payload=repr(payload)[:30]), self.assertRaises(ValueError):
                gate.extract_complete_completion(payload)

    def test_rejects_nonterminal_finish_reason_even_for_valid_json(self):
        for reason in (None, '', 'length', 'content_filter', 'tool_calls', 'function_call'):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                gate.extract_complete_completion(response(finish_reason=reason))

    def test_rejects_nonassistant_role(self):
        for role in (None, 'tool', 'system', 'user'):
            with self.subTest(role=role), self.assertRaises(ValueError):
                gate.extract_complete_completion(response(message={'role': role, 'content': '{"ok":true}'}))

    def test_rejects_refusal_and_tool_calls(self):
        for key, value in (('refusal', 'denied'), ('tool_calls', [{'id': 'tool-1'}]),
                           ('function_call', {'name': 'test'})):
            with self.subTest(key=key), self.assertRaises(ValueError):
                gate.extract_complete_completion(response(message={'role': 'assistant',
                    'content': '{"ok":true}', key: value}))

    def test_rejects_missing_or_nontext_content(self):
        for content in (None, '', '  ', [], {'ok': True}):
            with self.subTest(content=repr(content)), self.assertRaises(ValueError):
                gate.extract_complete_completion(response(content=content))

    def test_analyst_truncated_valid_json_is_http_502(self):
        payload = response(json.dumps(analyst_json()), finish_reason='length')
        with patch.object(ai, 'BASE', 'http://fixture/v1'), patch.object(ai, 'MODEL', 'fixture'), \
             patch.object(ai.requests, 'post', return_value=mock_response(payload)) as post:
            with self.assertRaises(HTTPException) as caught:
                ai.call_model('synthetic', {}, ai.Analyst)
        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(post.call_count, 1)

    def test_critic_schema_retry_must_also_finish(self):
        original = response(json.dumps(critic_json(extra=True)))
        repaired = response(json.dumps(critic_json()), finish_reason='content_filter')
        with patch.object(ai, 'BASE', 'http://fixture/v1'), patch.object(ai, 'MODEL', 'fixture'), \
             patch.object(ai.requests, 'post', side_effect=[mock_response(original), mock_response(repaired)]) as post:
            with self.assertRaises(HTTPException) as caught:
                ai.call_model('synthetic', {}, ai.Critique)
        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(post.call_count, 2)

    def test_completed_analyst_reaches_schema_validation(self):
        payload = response(json.dumps(analyst_json()))
        with patch.object(ai, 'BASE', 'http://fixture/v1'), patch.object(ai, 'MODEL', 'fixture'), \
             patch.object(ai.requests, 'post', return_value=mock_response(payload)):
            self.assertEqual(ai.call_model('synthetic', {}, ai.Analyst).severity, 'P1')


if __name__ == '__main__':
    unittest.main()
