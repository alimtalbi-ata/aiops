"""Disposable pure tests for the real-host read-only portal qualification path."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy' / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


canon = load('portal_canonical', 'debian-portal-canonicalize.py')
host = load('portal_host', 'debian-portal-host-contracts.py')
PIN = '1fd6391f8a8e7129246ec1b9e4a0d6d4c4eed688'
BASE = """name: aiops2
services:
  aiops2-core:
    image: core:test
  aiops2-portal:
    build: {context: ./app, dockerfile: portal/Dockerfile}
    container_name: aiops2-rebuild-portal
    environment:
      CORE_URL: http://aiops2-core:810
    ports: ["0.0.0.0:7777:777"]
  aiops2-twin:
    image: twin:test
"""


class FakeResponse:
    def __init__(self, status, body, content_type='application/json'):
        self.status = status
        self.data = body.encode()
        self.headers = {'Content-Type': content_type,
                        'Cache-Control': 'no-store',
                        'X-Content-Type-Options': 'nosniff'}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.data[:size]


class FakeOpener:
    def __init__(self, response):
        self.response = response
    def open(self, req, timeout=4):
        assert req.get_method() == 'GET'
        assert req.full_url.startswith('http://127.0.0.1:7777/')
        assert not req.has_header('Authorization')
        return self.response


class DebianPortalQualification(unittest.TestCase):
    def test_canonical_patch_is_scoped_and_idempotent(self):
        updated, tag = canon.canonical_text(BASE, PIN)
        self.assertIn('image: "' + tag + '"', updated)
        self.assertIn('AIOPS_PORTAL_HOST_PORT: "7777"', updated)
        self.assertEqual(updated.count('AIOPS_PORTAL_HOST_PORT'), 1)
        self.assertIn('  aiops2-core:\n    image: core:test', updated)
        self.assertIn('  aiops2-twin:\n    image: twin:test', updated)
        self.assertEqual(canon.canonical_text(updated, PIN), (updated, tag))

    def test_canonical_rejects_conflict_or_ambiguous_blocks(self):
        with self.assertRaisesRegex(ValueError, 'PORTAL_PORT_CONFLICT'):
            canon.canonical_text(BASE.replace('      CORE_URL:',
                '      AIOPS_PORTAL_HOST_PORT: "17777"\n      CORE_URL:'), PIN)
        with self.assertRaisesRegex(ValueError, 'PORTAL_IMAGE_CONFLICT'):
            canon.canonical_text(BASE.replace('    build:',
                '    image: foreign:tag\n    build:'), PIN)
        with self.assertRaisesRegex(ValueError, 'PORTAL_BLOCK_AMBIGUOUS'):
            canon.canonical_text(BASE + '  aiops2-portal:\n', PIN)

    def test_nine_anonymous_routes_are_get_only(self):
        self.assertEqual(len(host.CASES), 9)
        self.assertEqual(len(set(x[1] for x in host.CASES)), 9)
        self.assertTrue(all(path.startswith('/') for _, path, _ in host.CASES))
        self.assertNotIn('/api/demo', [x[1] for x in host.CASES])

    def test_health_requires_numeric_7777(self):
        case = host.CASES[0]
        good = FakeResponse(200, json.dumps({'status': 'ok', 'external_port': 7777}))
        self.assertEqual(host.qualify(case, FakeOpener(good))['status'], 'PASS')
        for wrong in ('7777', 17777, True):
            bad = FakeResponse(200, json.dumps({'status': 'ok', 'external_port': wrong}))
            self.assertEqual(host.qualify(case, FakeOpener(bad))['status'], 'FAIL')

    def test_human_allow_never_promoted(self):
        case = next(x for x in host.CASES if x[0] == 'glpi_authority')
        denied = FakeResponse(503, json.dumps({'state': 'UNKNOWN',
                                                'human_authority': {'human_allow': False}}))
        self.assertEqual(host.qualify(case, FakeOpener(denied))['status'], 'PASS')
        forged = FakeResponse(200, json.dumps({'state': 'ALLOW',
                                                'human_authority': {'human_allow': True}}))
        self.assertEqual(host.qualify(case, FakeOpener(forged))['status'], 'FAIL')

    def test_security_headers_required(self):
        html = FakeResponse(200, '<html>UNKNOWN</html>', 'text/html')
        self.assertEqual(host.qualify(host.CASES[1], FakeOpener(html))['status'], 'PASS')
        html.headers.pop('Cache-Control')
        self.assertEqual(host.qualify(host.CASES[1], FakeOpener(html))['status'], 'FAIL')

    def test_entrypoint_is_single_existing_poller_and_no_destructive_commands(self):
        entry = (ROOT / 'deploy/deploy-demo-studio-v2.sh').read_text()
        self.assertIn('debian-portal-canonicalize.py', entry)
        self.assertIn('debian-portal-host-contracts.py', entry)
        self.assertIn('debian-portal-preflight.py', entry)
        for unsafe in ('docker stop', 'docker run', 'down -v', 'prune'):
            self.assertNotIn(unsafe, entry)


if __name__ == '__main__':
    unittest.main()
