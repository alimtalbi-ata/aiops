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


    def test_post_upgrade_live_image_readback_detects_drift(self):
        services = ('core', 'twin', 'policy', 'worker', 'simulator')
        images = [
            {'service': service, 'observed_image_id': 'sha256:' + 'a' * 64,
             'observed_container_id': 'b' * 64}
            for service in services
        ]
        class Host:
            def __init__(self):
                self.drift = False
            def inspect(self, name):
                return {
                    'inspection': 'READ_ONLY', 'compose_project': 'aiops2-rebuild',
                    'state': 'running', 'health': 'healthy',
                    'image_id': 'sha256:' + ('c' if self.drift and name.endswith('worker')
                                            else 'a') * 64,
                    'container_id': 'b' * 64,
                    'environment': 'SYNTHETIC_SECRET_NEVER_PUBLISH',
                }
        host = Host()
        verified = mod.acme_runtime_snapshot(host, images)
        self.assertEqual(verified['status'], 'PASS')
        self.assertEqual(len(verified['services']), 5)
        self.assertNotIn('SYNTHETIC_SECRET_NEVER_PUBLISH', json.dumps(verified))
        host.drift = True
        drift = mod.acme_runtime_snapshot(host, images)
        self.assertEqual(drift['status'], 'DRIFT_OR_UNKNOWN')
        self.assertFalse(next(x for x in drift['services']
                              if x['service'] == 'worker')['matches_upgrade_receipt'])
        self.assertEqual(mod.acme_runtime_snapshot(object(), images)['status'],
                         'NOT_VERIFIED')
        self.assertEqual(mod.acme_runtime_snapshot(host, images[:-1])['status'],
                         'NOT_VERIFIED')

    def test_upgrade_pass_requires_native_pg16_scratch_restore_proof(self):
        services = ('core', 'twin', 'policy', 'worker', 'simulator')
        images = [
            {'service': service, 'previous_image_id': 'sha256:' + 'c' * 64,
             'observed_image_id': 'sha256:' + 'a' * 64,
             'observed_container_id': 'b' * 64, 'observed_health': 'healthy',
             'image_changed': True, 'http_status': 200, 'json_status': 'ok'}
            for service in services
        ]
        class Host(FakePoller):
            def inspect(self, name):
                return {'inspection': 'READ_ONLY',
                        'compose_project': 'aiops2-rebuild',
                        'state': 'running', 'health': 'healthy',
                        'image_id': 'sha256:' + 'a' * 64,
                        'container_id': 'b' * 64}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'deploy').mkdir()
            (root / 'deploy/debian-acme-sandbox-release.json').write_text(
                json.dumps({'enabled': True, 'candidate_sha': 'a' * 40}))
            receipt = {
                'schema': 'aiops.debian-acme-sandbox-upgrade.v1',
                'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'source_sha': 'a' * 40, 'status': 'PASS', 'exit_code': 0,
                'docker_container_mutations': 1, 'docker_image_builds': 5,
                'portal_7777_untouched': True, 'glpi_write': False,
                'live_effects_allowed': False, 'rollback_status': 'NOT_REQUIRED',
                'pg16_backup_sha256': 'd' * 64,
                'portal_http': {'http_status': 200, 'json_status': 'ok',
                                'external_port': 7777}, 'images': images,
            }
            path = root / 'acme-sandbox-upgrade.json'
            host = Host()
            host.REPORT_GIT = root
            original_root = mod.ROOT
            mod.ROOT = root
            try:
                def report():
                    return mod.make_receipt(
                        host, state=root, dev=root, env=root / 'missing',
                        manifest_path=root / 'missing',
                        run=lambda argv, **kwargs: subprocess.CompletedProcess(
                            argv, 1, stdout='', stderr=''))
                path.write_text(json.dumps(receipt))
                missing = report()
                self.assertEqual(missing['acme_sandbox_upgrade']['status'],
                                 'NOT_VERIFIED')
                self.assertEqual(missing['acme_sandbox_runtime']['status'],
                                 'NOT_VERIFIED')
                receipt['pg16_scratch_restore'] = 'PASS'
                path.write_text(json.dumps(receipt))
                good = report()
                self.assertEqual(good['acme_sandbox_upgrade']['status'], 'PASS')
                self.assertEqual(good['acme_sandbox_upgrade']['pg16_scratch_restore'],
                                 'PASS')
                self.assertEqual(good['acme_sandbox_runtime']['status'], 'PASS')
                self.assertFalse(good['acme_sandbox_upgrade']['historical_receipt'])
                # An older receipt must not hide the present live Docker readback.
                # E2E still needs its own fresh, independently verified receipt.
                receipt['collected_at'] = (dt.datetime.now(dt.timezone.utc)
                    - dt.timedelta(minutes=45)).isoformat()
                path.write_text(json.dumps(receipt))
                historical = report()
                self.assertEqual(historical['acme_sandbox_upgrade']['status'], 'PASS')
                self.assertTrue(historical['acme_sandbox_upgrade']['historical_receipt'])
                self.assertEqual(historical['acme_sandbox_runtime']['status'], 'PASS')
                self.assertEqual(historical['acme_sandbox_verdict'],
                                 'NO_GO_NOT_RUNTIME_VERIFIED')
                self.assertEqual(good['acme_sandbox_verdict'],
                                 'NO_GO_NOT_RUNTIME_VERIFIED')
            finally:
                mod.ROOT = original_root

    def test_entrypoint_requires_pinned_deploy_and_receipt(self):
        entry = (ROOT / 'deploy/deploy-demo-studio-v2.sh').read_text()
        deploy = (ROOT / 'deploy/debian-portal-deploy.sh').read_text()
        self.assertEqual(subprocess.run(
            ['bash', '-n', str(ROOT / 'deploy/deploy-demo-studio-v2.sh')],
            capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(
            ['bash', '-n', str(ROOT / 'deploy/debian-portal-deploy.sh')],
            capture_output=True).returncode, 0)
        self.assertIn('debian-portal-deploy.sh', entry)
        self.assertIn('debian-portal-preflight.py', entry)
        self.assertIn('flock -n', deploy)
        self.assertIn('SOURCE_SHA_CHANGED', deploy)
        self.assertIn('portal-rollback-manifest.json', deploy)
        self.assertIn('portal-deploy-result.json', deploy)
        self.assertIn('NOOP_ALREADY_SAME_IMAGE', deploy)
        self.assertIn('NOOP_PINNED_RUNNING_IMAGE', deploy)
        self.assertIn('debian-portal-playwright-snapshot.py', entry)
        self.assertIn('--assert-host SRV-DEB-05', entry)
        self.assertIn('playwright==1.55.0', entry)
        self.assertIn('chromium --only-shell', entry.replace('\\\n', ' '))
        self.assertIn('HOST_PLAYWRIGHT_BOOTSTRAP_PIP_FAILED', entry)
        self.assertNotIn('sudo apt', entry)
        self.assertIn('--no-deps --no-build', deploy)
        self.assertNotIn('docker stop', deploy)
        self.assertNotIn('docker run', deploy)
        self.assertNotIn('down -v', deploy)
        self.assertNotIn('prune', deploy)

    def test_deploy_receipt_requires_exact_sha_image_and_strict_host_health(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'manifest.json').write_text(json.dumps({
                'enabled': True, 'candidate_sha': 'a' * 40}))
            (p / 'portal-deploy-result.json').write_text(json.dumps({
                'schema': 'aiops.debian-portal-deploy-result.v1',
                'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'candidate_sha': 'a' * 40, 'status': 'PASS',
                'deployment_executed': True, 'docker_mutations': 1,
                'new_image_id': 'sha256:' + 'a' * 64,
                'rollback_attempted': False}))
            fake = FakePoller(good=True)
            fake.REPORT_GIT = p
            r = mod.make_receipt(fake, manifest_path=p / 'manifest.json',
                                 dev=p, env=p / '.env', state=p)
            self.assertEqual(r['deployment_preflight']['verdict'],
                             'DEPLOYED_HEALTH_PASS_E2E_PENDING')
            self.assertTrue(r['deployment_preflight']['deployment_executed'])
            self.assertEqual(r['release_stable'], 'NO_GO')
            fake.good = False
            r = mod.make_receipt(fake, manifest_path=p / 'manifest.json',
                                 dev=p, env=p / '.env', state=p)
            self.assertEqual(r['deployment_preflight']['verdict'],
                             'NO_GO_DEPLOY_FAILED_OR_NOT_OBSERVED')
            fake.good = True
            record = json.loads((p / 'portal-deploy-result.json').read_text())
            record['new_image_id'] = 'sha256:' + 'b' * 64
            (p / 'portal-deploy-result.json').write_text(json.dumps(record))
            r = mod.make_receipt(fake, manifest_path=p / 'manifest.json',
                                 dev=p, env=p / '.env', state=p)
            self.assertEqual(r['deployment_preflight']['verdict'],
                             'NO_GO_DEPLOY_FAILED_OR_NOT_OBSERVED')


    def test_host_browser_receipt_requires_exact_host_sha_image_and_private_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            folder = p / 'portal-playwright'
            folder.mkdir()
            now = dt.datetime.now(dt.timezone.utc)
            sha = 'a' * 40
            image = 'sha256:' + 'b' * 64
            names = ('01-overview','02-journey','03-runs','04-connections',
                     'demo-center','recorder-station','demo-studio','noc',
                     '09-mobile-overview')
            payload = {
                'schema': 'aiops.portal-host-playwright-snapshots.v1',
                'collected_at': now.isoformat(), 'host': 'SRV-DEB-05',
                'host_asserted': True, 'mode': 'ANONYMOUS_SYNTHETIC_UI_ONLY',
                'origin': 'http://127.0.0.1:7777',
                'stable_checkout_sha': sha, 'portal_image_id': image,
                'live_effects': 0, 'status': 'PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY',
                'real_screen_capture': 'NOT_VERIFIED', 'human_glpi_acl': 'NOT_VERIFIED',
                'n8n_login': 'NOT_VERIFIED', 'oidc_https': 'NOT_VERIFIED',
                'page_errors_count': 0, 'console_errors_count': 0,
                'failed_requests_count': 0, 'blocked_requests_count': 0,
                'checks': [{'name': 'check-%02d' % i, 'status': 'PASS'}
                           for i in range(11)],
                'screenshots': [{'name': n + '.png', 'bytes': 100,
                                 'sha256': 'c' * 64} for n in names],
                'secret': 'SYNTHETIC_SECRET_NEVER_EXPORT',
            }
            path = folder / 'portal-playwright-receipt.json'
            path.write_text(json.dumps(payload))
            result = mod.host_playwright_receipt(p, sha, image, now=now)
            self.assertEqual(result['status'], 'PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY')
            self.assertEqual(len(result['screenshots_sha256']), 9)
            self.assertNotIn('SYNTHETIC_SECRET_NEVER_EXPORT', json.dumps(result))
            self.assertEqual(mod.host_playwright_receipt(p, 'd' * 40, image, now=now),
                             {'status': 'NOT_VERIFIED'})
            payload['console_errors_count'] = 1
            path.write_text(json.dumps(payload))
            self.assertEqual(mod.host_playwright_receipt(p, sha, image, now=now),
                             {'status': 'NOT_VERIFIED'})
            payload['console_errors_count'] = 0
            payload['status'] = 'FAIL'
            payload['failure_type'] = 'ModuleNotFoundError'
            payload['failure_stage'] = 'IMPORT_PLAYWRIGHT'
            payload['console_error_category'] = 'FAVICON'
            payload['page_errors_count'] = 0
            path.write_text(json.dumps(payload))
            failed = mod.host_playwright_receipt(p, sha, image, now=now)
            self.assertEqual(failed['failure_type'], 'ModuleNotFoundError')
            self.assertEqual(failed['failure_stage'], 'IMPORT_PLAYWRIGHT')
            self.assertEqual(failed['console_error_category'], 'FAVICON')
            self.assertEqual(failed['page_errors_count'], 0)
            self.assertNotIn('SYNTHETIC_SECRET_NEVER_EXPORT', json.dumps(failed))
            payload['collected_at'] = (now - dt.timedelta(hours=1)).isoformat()
            path.write_text(json.dumps(payload))
            self.assertEqual(mod.host_playwright_receipt(p, sha, image, now=now),
                             {'status': 'NOT_VERIFIED'})


    def test_pinned_noop_receipt_is_not_falsely_classified_as_deployment(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            image = 'sha256:' + 'a' * 64
            (p / 'manifest.json').write_text(json.dumps({
                'enabled': True, 'candidate_sha': 'a' * 40}))
            (p / 'portal-deploy-result.json').write_text(json.dumps({
                'schema': 'aiops.debian-portal-deploy-result.v1',
                'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'candidate_sha': 'a' * 40, 'status': 'PASS',
                'deployment_executed': False, 'docker_mutations': 0,
                'previous_image_id': image, 'new_image_id': None,
                'rollback_attempted': False}))
            fake = FakePoller(good=True)
            fake.REPORT_GIT = p
            r = mod.make_receipt(fake, manifest_path=p / 'manifest.json',
                                 dev=p, env=p / '.env', state=p)
            self.assertEqual(r['deployment_preflight']['verdict'],
                             'ALREADY_PINNED_HEALTH_PASS_NO_MUTATION')
            self.assertFalse(r['deployment_preflight']['deployment_executed'])
            self.assertEqual(r['deployment_preflight']['docker_mutations'], 0)
            self.assertEqual(r['release_stable'], 'NO_GO')
            fake.good = False
            r = mod.make_receipt(fake, manifest_path=p / 'manifest.json',
                                 dev=p, env=p / '.env', state=p)
            self.assertEqual(r['deployment_preflight']['verdict'],
                             'NO_GO_DEPLOY_FAILED_OR_NOT_OBSERVED')


if __name__ == '__main__':
    unittest.main()
