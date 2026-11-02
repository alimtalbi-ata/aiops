"""Disposable preflight negative gates: no Docker or host execution."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'deploy/debian-portal-preflight.py'
spec = importlib.util.spec_from_file_location('preflight', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakePoller:
    def __init__(self, good=True):
        self.good = good
    def collect(self):
        return {'schema': 'aiops.debian-poller-qualification.v1',
                'host_portal_7777': 'PASS' if self.good else 'FAIL_OR_UNKNOWN',
                'http_7777': {'qualified': self.good},
                'portal': {'image_id': 'sha256:' + 'a' * 64},
                'release_stable': 'NO_GO'}


class PreflightContract(unittest.TestCase):
    def test_gate_fail_closed_without_host_or_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            r = mod.make_receipt(FakePoller(), manifest_path=p / 'missing', dev=p, env=p / 'missing')
        self.assertFalse(r['deployment_preflight']['deployment_executed'])
        self.assertEqual(r['deployment_preflight']['verdict'], 'NO_GO_DEPLOY_READONLY_PREFLIGHT')
        self.assertIsNone(r['deployment_preflight']['candidate_sha_pinned'])

    def test_valid_compose_is_still_no_go_without_backup_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'compose.yml').write_text('services: {}\n')
            (p / '.env').write_text('FAKE=1\n')
            (p / 'manifest.json').write_text(json.dumps({'enabled': False, 'candidate_sha': 'a' * 40}))
            calls = []
            def runner(argv, **kwargs):
                calls.append(argv)
                self.assertEqual(kwargs['capture_output'], True)
                return subprocess.CompletedProcess(argv, 0,
                    stdout='aiops2-portal\n' if argv[-1] == '--services' else '', stderr='SYNTHETIC_SECRET')
            r = mod.make_receipt(FakePoller(), manifest_path=p / 'manifest.json',
                                 run=runner, dev=p, env=p / '.env')
            self.assertEqual(len(calls), 2)
            self.assertEqual(r['deployment_preflight']['reason'], 'BACKUP_ROLLBACK_AND_E2E_GATES_MISSING')
            self.assertNotIn('SYNTHETIC_SECRET', json.dumps(r))
            self.assertFalse(r['deployment_preflight']['deployment_executed'])

    def test_entrypoint_is_only_readonly_preflight(self):
        entry = (ROOT / 'deploy/deploy-demo-studio-v2.sh').read_text()
        deploy = (ROOT / 'deploy/debian-portal-deploy.sh').read_text()
        self.assertEqual(subprocess.run(['bash', '-n', str(ROOT / 'deploy/deploy-demo-studio-v2.sh')], capture_output=True).returncode, 0)
        self.assertIn('debian-portal-preflight.py', entry)
        self.assertNotIn('debian-portal-deploy.sh', entry)
        self.assertNotIn('docker', entry)
        self.assertIn('NO_GO', deploy)
        self.assertNotIn('docker build', deploy)
        self.assertNotIn('docker compose', deploy)


if __name__ == '__main__':
    unittest.main()
