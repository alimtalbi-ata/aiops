#!/usr/bin/env python3
"""Read-only Debian Compose portal preflight; publish via existing SSH report checkout.

No build, Docker mutation, credentials, host shell, or GLPI write. A preflight
receipt is never a deployment approval or a tenant/human E2E attestation.
"""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'deploy/debian-poller-qualification.py'
MANIFEST = ROOT / 'deploy/debian-portal-release.json'
DEV = Path('/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e')
ENV = Path('/home/aiops/aiops-v28-demo/.env')
SHA = re.compile(r'[0-9a-f]{40}\Z')


def load_poller():
    spec = importlib.util.spec_from_file_location('aiops_debian_poller', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compose_status(run=subprocess.run, dev=DEV, env=ENV):
    """Discard all Compose output: interpolated config can contain secrets."""
    out = {'compose_file_present': (dev / 'compose.yml').is_file(),
           'env_file_present': env.is_file(),
           'compose_config_valid': False, 'portal_service_present': False,
           'portal_host_port_7777': False, 'portal_env_port_7777': False,
           'portal_container_name_matches': False}
    if not (out['compose_file_present'] and out['env_file_present']):
        return out
    base = ['docker', 'compose', '--project-name', 'aiops2-rebuild',
            '--env-file', str(env), '-f', str(dev / 'compose.yml')]
    try:
        config = run(base + ['config', '--quiet'], capture_output=True,
                     text=True, timeout=25, check=False)
        out['compose_config_valid'] = config.returncode == 0
        if out['compose_config_valid']:
            services = run(base + ['config', '--services'], capture_output=True,
                           text=True, timeout=25, check=False)
            out['portal_service_present'] = (services.returncode == 0 and
                                              'aiops2-portal' in services.stdout.splitlines())
            if out['portal_service_present']:
                # Parse in memory; NEVER log resolved Compose config (may contain secrets).
                config_json = run(base + ['config', '--format', 'json'], capture_output=True,
                                  text=True, timeout=25, check=False)
                if config_json.returncode == 0 and len(config_json.stdout) <= 262144:
                    try:
                        svc = json.loads(config_json.stdout)['services']['aiops2-portal']
                        ports = svc.get('ports') or []
                        out['portal_host_port_7777'] = any(
                            isinstance(p, dict) and str(p.get('published')) == '7777'
                            and str(p.get('target')) == '777'
                            and p.get('protocol', 'tcp') == 'tcp'
                            for p in ports)
                        env_map = svc.get('environment') or {}
                        out['portal_env_port_7777'] = (
                            isinstance(env_map, dict) and
                            str(env_map.get('AIOPS_PORTAL_HOST_PORT')) == '7777')
                        out['portal_container_name_matches'] = (
                            svc.get('container_name') == 'aiops2-rebuild-portal')
                    except (ValueError, TypeError, KeyError, AttributeError):
                        pass
    except (OSError, subprocess.TimeoutExpired):
        pass
    return out



def reporter_freshness(path, now=None):
    """Only the timestamp is read; never republish reporter inventory or secrets."""
    result = {'collected_at': None, 'age_seconds': None, 'fresh': False}
    try:
        if path.stat().st_size > 262144:
            return result
        data = json.loads(path.read_text(encoding='utf-8'))
        stamp = data.get('collected_at')
        when = dt.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if when.tzinfo is None:
            return result
        age = int(((now or dt.datetime.now(dt.timezone.utc)) - when).total_seconds())
        if age < 0 or age > 365 * 86400:
            return result
        result.update(collected_at=when.astimezone(dt.timezone.utc).isoformat(),
                      age_seconds=age, fresh=age <= 900)
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        pass
    return result


def make_receipt(poller, manifest_path=MANIFEST, run=subprocess.run, dev=DEV, env=ENV):
    report = poller.collect()
    pinned = None
    disabled = False
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        pinned = manifest.get('candidate_sha')
        disabled = manifest.get('enabled') is False
        if not isinstance(pinned, str) or not SHA.fullmatch(pinned):
            pinned = None
    except (OSError, ValueError, TypeError):
        pass
    compose = compose_status(run=run, dev=dev, env=env)
    reporter = reporter_freshness(getattr(poller, 'REPORT_GIT', Path('/nonexistent')) /
                                  'ops/debian-reports/SRV-DEB-05/latest.json')
    report['reporter_freshness'] = reporter
    healthy = (report.get('host_portal_7777') == 'PASS' and
               report.get('http_7777', {}).get('qualified') is True)
    report['deployment_preflight'] = {
        'schema': 'aiops.debian-portal-preflight.v1',
        'candidate_sha_pinned': pinned,
        'release_manifest_disabled': disabled,
        **compose,
        'canonical_portal_7777_healthy': healthy,
        'current_portal_image_id': report.get('portal', {}).get('image_id'),
        'backup_restoration_tested': False,
        'compose_rollback_tested': False,
        'deployment_executed': False,
        'docker_mutations': 0,
        'verdict': 'NO_GO_DEPLOY_READONLY_PREFLIGHT',
        'reason': ('REPORTER_STALE_OR_MISSING' if not reporter['fresh'] else
                   'SOURCE_OR_COMPOSE_UNQUALIFIED' if not (pinned and disabled and
                    compose['compose_config_valid'] and compose['portal_service_present'] and
                    compose['portal_host_port_7777'] and compose['portal_env_port_7777'] and
                    compose['portal_container_name_matches']) else
                   'PORTAL_HEALTH_CONTRACT_UNQUALIFIED' if not healthy else
                   'BACKUP_ROLLBACK_AND_E2E_GATES_MISSING'),
    }
    report['release_stable'] = 'NO_GO'
    report['execution'] = 'POLLER_ENTRYPOINT_READONLY_PREFLIGHT'
    return report


def main():
    try:
        poller = load_poller()
        report = make_receipt(poller)
        status = poller.publish(report)
        print('AIOPS_DEBIAN_PORTAL_PREFLIGHT_RECEIPT=' + status)
        print('AIOPS_DEBIAN_PORTAL_DEPLOY=NOT_EXECUTED')
        return 0
    except Exception as exc:
        print('AIOPS_DEBIAN_PORTAL_PREFLIGHT_RECEIPT=FAILED reason=' + type(exc).__name__, file=sys.stderr)
        return 78


if __name__ == '__main__':
    raise SystemExit(main())
