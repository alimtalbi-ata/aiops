#!/usr/bin/env python3
"""Read-only Debian Compose portal preflight; publish via existing SSH report checkout.

No build, Docker mutation, credentials, host shell, or GLPI write. A preflight
receipt is never a deployment approval or a tenant/human E2E attestation.
"""
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
           'compose_config_valid': False, 'portal_service_present': False}
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
    except (OSError, subprocess.TimeoutExpired):
        pass
    return out


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
        'reason': ('SOURCE_OR_COMPOSE_UNQUALIFIED' if not (pinned and disabled and
                    compose['compose_config_valid'] and compose['portal_service_present'] and healthy)
                   else 'BACKUP_ROLLBACK_AND_E2E_GATES_MISSING'),
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
