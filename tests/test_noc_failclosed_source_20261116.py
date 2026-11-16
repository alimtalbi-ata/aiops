"""Offline NOC prototype safety regression; no network or runtime dependencies.

Run: python -m unittest -v tests/test_noc_failclosed_source_20261116.py
This checks source invariants, not browser behavior or runtime policy.
"""
from html.parser import HTMLParser
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'docs/ux/prototypes/noc_decision_sandbox_20261116.html'

class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = []
        self.ids = set()
        self.buttons = []
        self.status = 0
        self.external = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.add(a['id'])
        if tag == 'section':
            self.sections.append(a.get('aria-labelledby'))
        if tag == 'button':
            self.buttons.append(a.get('id'))
        if a.get('role') == 'status':
            self.status += 1
        if tag in ('script', 'iframe', 'img', 'link') and (a.get('src') or a.get('href')):
            self.external.append((tag, a.get('src') or a.get('href')))

class TestNocFailClosedSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding='utf-8')
        cls.dom = Structure()
        cls.dom.feed(cls.source)

    def test_six_labelled_decision_sections(self):
        self.assertEqual(len(self.dom.sections), 6)
        self.assertEqual(len(set(self.dom.sections)), 6)
        self.assertTrue(all(label in self.dom.ids for label in self.dom.sections))

    def test_safety_disclosure_visible_in_source(self):
        for token in ('SIMULATION', 'DENY_LIVE', 'NO-GO LIVE', 'UNKNOWN', 'HITL'):
            with self.subTest(token=token):
                self.assertIn(token, self.source)

    def test_no_external_resource_or_api_call(self):
        self.assertEqual(self.dom.external, [])
        self.assertNotRegex(self.source, r'\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon)\s*\(')
        self.assertNotRegex(self.source, r'\b(?:localStorage|sessionStorage)\b')

    def test_one_local_action_and_status(self):
        self.assertEqual(self.dom.buttons, ['prepare'])
        self.assertEqual(self.dom.status, 1)
        self.assertIn('Aucune transmission', self.source)
        self.assertNotRegex(self.source, r'\b(?:submit|window\.open|location\.assign)\s*\(')

if __name__ == '__main__':
    unittest.main()
