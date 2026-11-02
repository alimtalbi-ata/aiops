"""Disposable preflight negative gates: no Docker or host execution."""
import datetime as dt
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
            latest = p / 'ops/debian-reports/SRV-DEB-05/latest.json'
            latest.parent.mkdir(parents=True)
            latest.write_text(json.dumps({'collected_at': dt.datetime.now(dt.timezone.utc).isoformat()}))
            calls = []
            def runner(argv, **kwargs):
                calls.append(argv)
                self.assertEqual(kwargs['capture_output'], True)
                if argv[-2:] == ['--format', 'json']:
                    return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({
                        'services': {'aiops2-portal': {
                            'container_name': 'aiops2-rebuild-portal',
                            'environment': {'AIOPS_PORTAL_HOST_PORT': '7777',
                                            'A_SECRET': 'SYNTHETIC_SECRET'},
                            'ports': [{'published': '7777', 'target': 777, 'protocol': 'tcp'}]}}}))
                return subprocess.CompletedProcess(argv, 0,
                    stdout='aiops2-portal\n' if argv[-1] == '--services' else '',
                    stderr='SYNTHETIC_SECRET')
            fake = FakePoller()
            fake.REPORT_GIT = p
            (p / 'latest.json').write_text(json.dumps({
                'collected_at': dt.datetime.now(dt.timezone.utc).isoformat()}))
            (p / 'publish.log').write_text('REPORT_PUBLISH=PUBLISHED\\n')
            r = mod.make_receipt(fake, manifest_path=p / 'manifest.json',
                                 run=runner, dev=p, env=p / '.env', state=p)
            self.assertEqual(len(calls), 4)
            self.assertTrue(r['reporter_freshness']['fresh'])
            self.assertTrue(r['deployment_preflight']['portal_host_port_7777'])
            self.assertTrue(r['deployment_preflight']['portal_env_port_7777'])
            self.assertTrue(r['deployment_preflight']['portal_container_name_matches'])
            self.assertEqual(r['deployment_preflight']['reason'], 'BACKUP_ROLLBACK_AND_E2E_GATES_MISSING')
            self.assertNotIn('SYNTHETIC_SECRET', json.dumps(r))
            self.assertFalse(r['deployment_preflight']['deployment_executed'])

    def test_reporter_stale_and_bad_compose_port_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            latest = p / 'latest.json'
            now = dt.datetime(2026, 11, 2, 12, 18, tzinfo=dt.timezone.utc)
            latest.write_text(json.dumps({'collected_at': '2026-11-02T11:01:01Z'}))
            stale = mod.reporter_freshness(latest, now=now)
            self.assertFalse(stale['fresh'])
            self.assertGreater(stale['age_seconds'], 3600)
            latest.write_text(json.dumps({'collected_at': '2026-11-02T12:17:00Z'}))
            self.assertTrue(mod.reporter_freshness(latest, now=now)['fresh'])
            (p / 'compose.yml').write_text('services: {}\n')
            (p / '.env').write_text('FAKE=1\n')
            def runner(argv, **kwargs):
                if argv[-2:] == ['--format', 'json']:
                    return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({
                        'services': {'aiops2-portal': {
                            'container_name': 'aiops2-rebuild-portal',
                            'environment': {'AIOPS_PORTAL_HOST_PORT': '17777'},
                            'ports': [{'published': '17777', 'target': 777, 'protocol': 'tcp'}]}}}))
                return subprocess.CompletedProcess(argv, 0,
                    stdout='aiops2-portal\n' if argv[-1] == '--services' else '')
            flags = mod.compose_status(run=runner, dev=p, env=p / '.env')
            self.assertFalse(flags['portal_host_port_7777'])
            self.assertFalse(flags['portal_env_port_7777'])

    def test_local_collection_vs_publisher_stale_and_log_redaction(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            now = dt.datetime.now(dt.timezone.utc)
            (p / 'latest.json').write_text(json.dumps({
                'collected_at': now.isoformat()}))
            (p / 'publish.log').write_text(
                'PRIVATE_SYNTHETIC_TOKEN=do_not_publish\n'
                'REPORT_PUBLISH=FAILED reason=push_rejected\n')
            report = mod.local_reporter_pipeline(p, now=now)
            self.assertTrue(report['local_report']['fresh'])
            self.assertTrue(report['publish_log_recent'])
            self.assertEqual(report['publish_last_class'], 'PUSH_REJECTED')
            self.assertNotIn('PRIVATE_SYNTHETIC_TOKEN', json.dumps(report))
            (p / 'latest.json').write_text(json.dumps({
                'collected_at': '2026-11-02T11:01:01Z'}))
            old = mod.local_reporter_pipeline(p, now=dt.datetime(
                2026, 11, 2, 12, 24, tzinfo=dt.timezone.utc))
            self.assertFalse(old['local_report']['fresh'])


    def test_publisher_cron_diagnostics_never_exposes_crontab_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            script = home / '.local/bin/aiops-publish-report'
            script.parent.mkdir(parents=True)
            script.write_text('#!/bin/sh\necho PUBLISHED\n')
            script.chmod(0o700)
            calls = []
            def runner(argv, **kwargs):
                calls.append((argv, kwargs))
                return subprocess.CompletedProcess(argv, 0,
                    stdout='* * * * * flock -n /tmp/pub ~/.local/bin/aiops-publish-report TOKEN=SYNTHETIC_SECRET\n'
                           '* * * * * aiops-debian-reporter\n'
                           '* * * * * /home/aiops/aiops2-auto-deploy/poll.sh\n'
                           '# * * * * * aiops-publish-report\n')
            result = mod.publisher_cron_diagnostics(run=runner, home=home)
            self.assertTrue(result['cron_read_ok'])
            self.assertEqual(result['publisher_entry_count'], 1)
            self.assertEqual(result['reporter_entry_count'], 1)
            self.assertEqual(result['poller_entry_count'], 1)
            self.assertTrue(result['publisher_script_present'])
            self.assertTrue(result['publisher_script_executable'])
            self.assertEqual(len(result['publisher_script_sha256']), 64)
            self.assertNotIn('SYNTHETIC_SECRET', json.dumps(result))
            self.assertEqual(calls[0][0], ['crontab', '-l'])
            self.assertTrue(calls[0][1]['capture_output'])

    def test_publisher_cron_diagnostics_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            def runner(argv, **kwargs):
                return subprocess.CompletedProcess(argv, 1, stdout='NO CRONTAB')
            result = mod.publisher_cron_diagnostics(run=runner, home=Path(td))
            self.assertFalse(result['cron_read_ok'])
            self.assertIsNone(result['publisher_entry_count'])
            self.assertFalse(result['publisher_script_present'])

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
