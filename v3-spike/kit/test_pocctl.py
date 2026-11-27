"""Offline command contract tests. Real service qualification lives in CI."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from pocctl import Lifecycle, BASE


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.calls = []
        self.preflights = []
        self.fail_list = False
        self.health_state = 'healthy'
        self.ctl = Lifecycle(self.root, env={'DOCKER_HOST': 'test', 'COMPOSE_FILE': 'foreign',
            'COMPOSE_PROFILES': 'foreign', 'V3_DB_PASSWORD': 'foreign', 'V3_LAB_TOKEN': 'foreign'},
            run=self.run_fake, preflight=lambda root, **kw: self.preflights.append((root, kw)))

    def seed(self):
        envfile = self.root / 'poc.env'
        envfile.write_text('V3_DB_PASSWORD=' + 'a'*48 + '\nV3_LAB_TOKEN=' + 'b'*64 + '\n')
        envfile.chmod(0o600)

    def run_fake(self, args, **kw):
        self.calls.append((args, dict(kw['env'])))
        if args[0] == 'bash':
            self.seed()
        elif 'pg_dump' in args:
            kw['stdout'].write(b'PGDMP-test-fixture')
        elif 'pg_restore' in args:
            self.assertEqual(kw['stdin'].read(), b'PGDMP-test-fixture')
            if self.fail_list:
                raise subprocess.CalledProcessError(1, args)
        elif 'ps' in args:
            return subprocess.CompletedProcess(args, 0, stdout='a'*64+'\n')
        elif 'inspect' in args:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
                'Status': 'running', 'Health': {'Status': self.health_state}}) + ' ' + json.dumps(self.ctl.project))
        return subprocess.CompletedProcess(args, 0)

    def test_install_once_and_sanitized_environment(self):
        self.assertEqual(self.preflights[0][0], self.root)
        env = self.preflights[0][1]['env']
        for name in ('COMPOSE_FILE', 'COMPOSE_PROFILES', 'V3_DB_PASSWORD', 'V3_LAB_TOKEN'):
            self.assertNotIn(name, env)
        self.ctl.install()
        with self.assertRaises(ValueError):
            self.ctl.install()
        self.assertEqual(len(self.calls), 1)

    def test_start_never_builds_or_seeds_stop_never_deletes(self):
        self.seed()
        self.ctl.start()
        self.ctl.stop()
        start, stop = (a for a, _ in self.calls)
        self.assertIn('--no-build', start)
        self.assertEqual(start[start.index('--pull')+1], 'never')
        self.assertIn('stop', stop)
        self.assertIn('orchestration', stop)
        self.assertNotIn('down', stop)
        self.assertNotIn('-v', stop)

    def test_health_refuses_unhealthy_service(self):
        self.seed()
        report = self.ctl.health()
        self.assertEqual(report['services'], dict.fromkeys(BASE, 'healthy'))
        self.assertFalse(report['gamma_qualified'])
        self.health_state = 'unhealthy'
        with self.assertRaises(ValueError):
            self.ctl.health()

    def test_backup_verified_archive_and_failed_list_no_publication(self):
        self.seed()
        result = self.ctl.backup()
        path = Path(result['archive'])
        self.assertEqual(path.read_bytes(), b'PGDMP-test-fixture')
        self.assertEqual(result['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(result['restore_tested'])
        self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.fail_list = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.ctl.backup()
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_missing_or_public_credentials_fail_before_docker(self):
        with self.assertRaises(OSError):
            self.ctl.start()
        self.seed()
        (self.root / 'poc.env').chmod(0o644)
        with self.assertRaises(ValueError):
            self.ctl.start()
        self.assertEqual(self.calls, [])

    def test_guarded_gamma_never_falls_back_to_legacy(self):
        self.seed()
        (self.root / 'collector-control').mkdir()
        for bad in (None, 7770, 7777, 7790, 80):
            with self.assertRaises(ValueError):
                self.ctl.gamma(port=bad)
        self.assertEqual(self.calls, [])
        self.ctl.gamma(port=18081)
        args, env = self.calls[-1]
        self.assertEqual(args[-1], '--guarded-collector')
        self.assertEqual(env['V3_GUARDED_GAMMA_PORT'], '18081')


if __name__ == '__main__':
    unittest.main()
