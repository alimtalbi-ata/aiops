#!/usr/bin/env python3
"""Read-only Debian Compose portal preflight; publish via existing SSH report checkout.

No build, Docker mutation, credentials, host shell, or GLPI write. A preflight
receipt is never a deployment approval or a tenant/human E2E attestation.
"""
import datetime as dt
import importlib.util
import hashlib
import os
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



def classify_publisher_freshness(status):
    """A historical PUBLISHED line is not a current delivery acknowledgement."""
    state = dict(status)
    last = state.get('publish_last_class')
    if not state.get('local_report', {}).get('fresh'):
        delivery = 'LOCAL_REPORT_STALE'
    elif not state.get('publish_log_recent'):
        delivery = 'PUBLISH_LOG_STALE'
    elif last in ('DIRTY_CHECKOUT', 'MISSING_LOCAL_REPORT', 'PUSH_REJECTED',
                  'SSH_DENIED', 'SSH_DNS_FAILURE', 'GIT_FATAL'):
        delivery = 'PUBLISH_FAILURE'
    elif last in ('PUBLISHED', 'UNCHANGED'):
        delivery = 'RECENT_LOCAL_PUBLISH_ACTIVITY_ONLY'
    else:
        delivery = 'PUBLISH_UNVERIFIED'
    state['delivery_state'] = delivery
    # A local log cannot independently attest GitHub branch publication.
    state['remote_receipt_verified'] = False
    return state


def local_reporter_pipeline(state, now=None):
    """Classify local collection vs SSH publisher without exposing log contents."""
    now = now or dt.datetime.now(dt.timezone.utc)
    local = reporter_freshness(state / 'latest.json', now=now)
    status = {'local_report': local, 'publish_log_age_seconds': None,
              'publish_log_recent': False, 'publish_last_class': 'UNKNOWN'}
    log = state / 'publish.log'
    try:
        stat = log.stat()
        age = int((now - dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc)).total_seconds())
        if age < 0 or age > 365 * 86400:
            return classify_publisher_freshness(status)
        status['publish_log_age_seconds'] = age
        status['publish_log_recent'] = age <= 900
        with log.open('rb') as handle:
            handle.seek(max(0, stat.st_size - 8192))
            tail = handle.read(8192).decode('utf-8', errors='replace')
        classes = (
            ('REPORT_PUBLISH=PUBLISHED', 'PUBLISHED'),
            ('REPORT_PUBLISH=UNCHANGED', 'UNCHANGED'),
            ('reason=dirty_checkout', 'DIRTY_CHECKOUT'),
            ('reason=missing_local_report', 'MISSING_LOCAL_REPORT'),
            ('reason=push_rejected', 'PUSH_REJECTED'),
            ('Permission denied', 'SSH_DENIED'),
            ('Could not resolve hostname', 'SSH_DNS_FAILURE'),
            ('fatal:', 'GIT_FATAL'),
        )
        for line in reversed(tail.splitlines()):
            for needle, label in classes:
                if needle in line:
                    status['publish_last_class'] = label
                    return classify_publisher_freshness(status)
    except (OSError, ValueError, TypeError):
        pass
    return classify_publisher_freshness(status)



def publisher_cron_diagnostics(run=subprocess.run, home=None):
    """Read-only cron/script evidence. Never publish raw crontab, script or logs."""
    home = home or Path.home()
    script = home / '.local/bin/aiops-publish-report'
    out = {'schema': 'aiops.debian-publisher-cron-diagnostic.v1',
           'cron_read_ok': False, 'publisher_entry_count': None,
           'reporter_entry_count': None, 'poller_entry_count': None,
           'publisher_script_present': False, 'publisher_script_executable': False,
           'publisher_script_sha256': None}
    try:
        if script.is_file() and not script.is_symlink():
            out['publisher_script_present'] = True
            out['publisher_script_executable'] = os.access(script, os.X_OK)
            if script.stat().st_size <= 65536:
                out['publisher_script_sha256'] = hashlib.sha256(script.read_bytes()).hexdigest()
        proc = run(['crontab', '-l'], capture_output=True, text=True,
                   timeout=8, check=False)
        if proc.returncode != 0 or len(proc.stdout) > 65536:
            return out
        lines = [line.strip() for line in proc.stdout.splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        out['cron_read_ok'] = True
        out['publisher_entry_count'] = sum('aiops-publish-report' in line for line in lines)
        out['reporter_entry_count'] = sum('aiops-debian-reporter' in line for line in lines)
        out['poller_entry_count'] = sum('poll.sh' in line for line in lines)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        pass
    return out



def acme_runtime_snapshot(poller, images):
    """Independent post-upgrade Docker readback, never a deployment action.

    The private upgrade receipt alone is historical evidence. Compare its five
    exact container IDs and image IDs against the containers running NOW.
    Do not expose Docker environment, labels, mounts, or secrets.
    """
    out = {'status': 'NOT_VERIFIED', 'services': []}
    expected_services = ('core', 'twin', 'policy', 'worker', 'simulator')
    inspector = getattr(poller, 'inspect', None)
    if (not callable(inspector) or type(images) is not list or len(images) != 5
            or {x.get('service') for x in images if type(x) is dict}
            != set(expected_services)):
        return out
    expected = {x['service']: x for x in images}
    for service in expected_services:
        prior = expected[service]
        try:
            observed = inspector('aiops2-rebuild-' + service)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            observed = {}
        if type(observed) is not dict:
            observed = {}
        image = observed.get('image_id')
        container = observed.get('container_id')
        match = (observed.get('inspection') == 'READ_ONLY'
                 and observed.get('compose_project') == 'aiops2-rebuild'
                 and observed.get('state') == 'running'
                 and observed.get('health') == 'healthy'
                 and isinstance(image, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', image)
                 and isinstance(container, str) and re.fullmatch(r'[0-9a-f]{64}', container)
                 and image == prior.get('observed_image_id')
                 and container == prior.get('observed_container_id'))
        out['services'].append({
            'service': service, 'image_id': image if isinstance(image, str)
            and re.fullmatch(r'sha256:[0-9a-f]{64}', image) else None,
            'container_id': container if isinstance(container, str)
            and re.fullmatch(r'[0-9a-f]{64}', container) else None,
            'health': observed.get('health') if observed.get('health')
            in ('healthy', 'unhealthy', 'starting') else 'UNKNOWN',
            'matches_upgrade_receipt': bool(match),
        })
    out['status'] = ('PASS' if all(x['matches_upgrade_receipt']
                                  for x in out['services']) else 'DRIFT_OR_UNKNOWN')
    return out



def host_playwright_receipt(state, stable_sha, portal_image, now=None):
    """Publish only bounded, independently correlated host-browser metadata.

    PNG bytes stay private on Debian until operator review. A CI screenshot,
    stale receipt, missing provenance or anonymous HTTP cannot qualify OIDC.
    """
    out = {'status': 'NOT_VERIFIED'}
    try:
        path = state / 'portal-playwright/portal-playwright-receipt.json'
        if path.stat().st_size > 8192:
            return out
        local = json.loads(path.read_text(encoding='utf-8'))
        when = dt.datetime.fromisoformat(local['collected_at'].replace('Z', '+00:00'))
        age = ((now or dt.datetime.now(dt.timezone.utc)) - when).total_seconds()
        if (when.tzinfo is None or not 0 <= age <= 900
                or local.get('schema') != 'aiops.portal-host-playwright-snapshots.v1'
                or local.get('host', '').split('.')[0].casefold() != 'srv-deb-05'
                or local.get('host_asserted') is not True
                or local.get('mode') != 'ANONYMOUS_SYNTHETIC_UI_ONLY'
                or local.get('origin') != 'http://127.0.0.1:7777'
                or local.get('stable_checkout_sha') != stable_sha
                or not isinstance(stable_sha, str) or not SHA.fullmatch(stable_sha)
                or local.get('portal_image_id') != portal_image
                or not isinstance(portal_image, str)
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', portal_image)
                or local.get('live_effects') != 0):
            return out
        if local.get('status') == 'FAIL':
            failure = local.get('failure_type')
            stage = local.get('failure_stage')
            counts = {k: local.get(k) for k in (
                'page_errors_count', 'console_errors_count',
                'failed_requests_count', 'blocked_requests_count')}
            # Never export raw console text, request URLs or browser errors.
            allowed = {
                'console_error_class': {'none', 'http_401_resource',
                                        'http_404_resource', 'csp_rejected',
                                        'other_console_error'},
                'failed_request_class': {'none', 'aborted', 'connection',
                                         'other_request_failure'},
            }
            safe = {k: local.get(k) if type(local.get(k)) is str
                    and local.get(k) in choices else 'UNKNOWN'
                    for k, choices in allowed.items()}
            for k in ('console_error_stage', 'failed_request_stage'):
                value = local.get(k)
                safe[k] = value if type(value) is str and re.fullmatch(
                    r'[A-Za-z0-9_-]{3,50}', value) else 'UNKNOWN'
            return {'status': 'FAIL', 'collected_at': local['collected_at'],
                    **safe,
                    'failure_type': failure if isinstance(failure, str)
                    and re.fullmatch(r'[A-Za-z]{3,50}', failure) else 'UNKNOWN',
                    'failure_stage': stage if isinstance(stage, str)
                    and re.fullmatch(r'[A-Za-z0-9_-]{3,50}', stage) else 'UNKNOWN',
                    **{k: v if type(v) is int and 0 <= v <= 1000 else None
                       for k, v in counts.items()},
                    'stable_checkout_sha': stable_sha, 'portal_image_id': portal_image}
        if (local.get('status') != 'PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY'
                or local.get('real_screen_capture') != 'NOT_VERIFIED'
                or local.get('human_glpi_acl') != 'NOT_VERIFIED'
                or local.get('n8n_login') != 'NOT_VERIFIED'
                or local.get('oidc_https') != 'NOT_VERIFIED'
                or any(type(local.get(k)) is not int or local[k] != 0 for k in
                       ('page_errors_count','unexpected_console_errors_count',
                        'failed_requests_count','blocked_requests_count'))
                or type(local.get('expected_session_401_console_count')) is not int
                or local['expected_session_401_console_count'] not in (0, 1)
                or local.get('console_errors_count') !=
                   local['expected_session_401_console_count']):
            return out
        checks, shots = local.get('checks'), local.get('screenshots')
        expected = {'01-overview.png','02-journey.png','03-runs.png',
                    '04-connections.png','demo-center.png',
                    'recorder-station.png','demo-studio.png','noc.png',
                    '09-mobile-overview.png'}
        if (not isinstance(checks, list) or len(checks) < 11 or len(checks) > 20
                or any(type(x) is not dict or x.get('status') != 'PASS'
                       or not isinstance(x.get('name'), str)
                       or not re.fullmatch(r'[a-z0-9-]{3,50}', x['name'])
                       for x in checks)
                or not isinstance(shots, list) or len(shots) != 9
                or {x.get('name') for x in shots if type(x) is dict} != expected
                or any(type(x) is not dict
                       or type(x.get('bytes')) is not int or x['bytes'] <= 0
                       or x['bytes'] > 10000000
                       or not isinstance(x.get('sha256'), str)
                       or not re.fullmatch(r'[0-9a-f]{64}', x['sha256'])
                       for x in shots)):
            return out
        return {
            'status': 'PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY',
            'collected_at': local['collected_at'],
            'stable_checkout_sha': stable_sha, 'portal_image_id': portal_image,
            'screenshots_sha256': [
                {'name': x['name'], 'sha256': x['sha256']} for x in shots],
            'checks_passed': len(checks), 'checks_total': len(checks),
            'page_errors_count': 0,
            'console_errors_count': local['console_errors_count'],
            'expected_session_401_console_count':
                local['expected_session_401_console_count'],
            'unexpected_console_errors_count': 0,
            'failed_requests_count': 0, 'blocked_requests_count': 0,
            'oidc_https': 'NOT_VERIFIED', 'real_screen_capture': 'NOT_VERIFIED',
            'human_glpi_acl': 'NOT_VERIFIED', 'n8n_login': 'NOT_VERIFIED',
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return out


def make_receipt(poller, manifest_path=MANIFEST, run=subprocess.run, dev=DEV, env=ENV, state=None):
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
    report['reporter_pipeline'] = local_reporter_pipeline(
        state or Path.home() / '.local/state/aiops-debian-agent')
    report['publisher_cron_diagnostics'] = publisher_cron_diagnostics(run=run)
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
        'reason': ('REPORTER_LOCAL_STALE_OR_MISSING' if not report['reporter_pipeline']['local_report']['fresh'] else
                   'REPORTER_PUBLISHER_STALE_OR_MISSING' if not reporter['fresh'] else
                   'SOURCE_OR_COMPOSE_UNQUALIFIED' if not (pinned and disabled and
                    compose['compose_config_valid'] and compose['portal_service_present'] and
                    compose['portal_host_port_7777'] and compose['portal_env_port_7777'] and
                    compose['portal_container_name_matches']) else
                   'PORTAL_HEALTH_CONTRACT_UNQUALIFIED' if not healthy else
                   'BACKUP_ROLLBACK_AND_E2E_GATES_MISSING'),
    }
    # The local deploy result is a separate attestation, not inferred from CI or HTTP.
    # Require fresh receipt, exact release SHA and observed container image/health.
    state_dir = state or Path.home() / '.local/state/aiops-debian-agent'
    try:
        result_path = state_dir / 'portal-deploy-result.json'
        if result_path.stat().st_size <= 8192:
            deployed = json.loads(result_path.read_text(encoding='utf-8'))
            when = dt.datetime.fromisoformat(deployed['collected_at'].replace('Z', '+00:00'))
            age = (dt.datetime.now(dt.timezone.utc) - when).total_seconds()
            if (when.tzinfo is not None and 0 <= age <= 900
                    and deployed.get('schema') == 'aiops.debian-portal-deploy-result.v1'
                    and deployed.get('candidate_sha') == pinned):
                passed = (deployed.get('status') == 'PASS'
                          and deployed.get('deployment_executed') is True
                          and deployed.get('docker_mutations', 0) >= 1
                          and deployed.get('new_image_id') == report.get('portal', {}).get('image_id')
                          and healthy)
                # A previously pinned image is an idempotent NOOP, not a failed
                # deploy and never a fresh Docker mutation.
                noop = (deployed.get('status') == 'PASS'
                        and deployed.get('deployment_executed') is False
                        and deployed.get('docker_mutations') == 0
                        and deployed.get('new_image_id') is None
                        and deployed.get('previous_image_id') ==
                            report.get('portal', {}).get('image_id')
                        and healthy)
                report['deployment_preflight'].update(
                    deployment_executed=bool(deployed.get('deployment_executed')),
                    docker_mutations=deployed.get('docker_mutations', 0),
                    rollback_attempted=bool(deployed.get('rollback_attempted')),
                    deployment_result_collected_at=deployed.get('collected_at'),
                    deployed_image_id=deployed.get('new_image_id'),
                    verdict=('DEPLOYED_HEALTH_PASS_E2E_PENDING' if passed else
                             'ALREADY_PINNED_HEALTH_PASS_NO_MUTATION' if noop else
                             'NO_GO_DEPLOY_FAILED_OR_NOT_OBSERVED'),
                    reason=('E2E_SANDBOX_SIMULATION_NOT_ATTESTED' if passed else
                            'NO_NEW_IMAGE_OR_CONTAINER_MUTATION' if noop else
                            'DEPLOYMENT_RECEIPT_OR_HOST_MISMATCH'))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    # Independent host-only receipts. Never turn a 503 fail-closed API response
    # into human GLPI/HITL authority, and never infer a Docker mutation from CI.
    for filename, schema, key in (
        ('portal-compose-result.json', 'aiops.debian-portal-compose-canonical.v1',
         'canonical_compose_receipt'),
        ('portal-host-contracts.json', 'aiops.debian-portal-anonymous-nine-contracts.v1',
         'portal_nine_readonly_contracts'),
    ):
        report[key] = {'status': 'NOT_VERIFIED'}
        try:
            local_path = state_dir / filename
            if local_path.stat().st_size > 16384:
                continue
            local = json.loads(local_path.read_text(encoding='utf-8'))
            when = dt.datetime.fromisoformat(local['collected_at'].replace('Z', '+00:00'))
            age = (dt.datetime.now(dt.timezone.utc) - when).total_seconds()
            if (when.tzinfo is None or not 0 <= age <= 900 or
                local.get('schema') != schema or
                local.get('image_id') != report.get('portal', {}).get('image_id') or
                not isinstance(local.get('image_id'), str)):
                continue
            if key == 'canonical_compose_receipt':
                if local.get('candidate_sha') != pinned:
                    continue
                report[key] = {k: local.get(k) for k in (
                    'collected_at', 'status', 'reason', 'compose_changed',
                    'docker_mutations', 'rollback_attempted', 'rollback_succeeded',
                    'base_compose_verified', 'portal_health_strict', 'image_id')}
            else:
                checks = local.get('checks')
                if (not isinstance(checks, list) or len(checks) != 9 or
                    local.get('total') != 9 or
                    not all(isinstance(c, dict) and c.get('status') in ('PASS', 'FAIL')
                            for c in checks)):
                    continue
                report[key] = {
                    'collected_at': local.get('collected_at'),
                    'status': local.get('verdict'),
                    'attempt_id': local.get('attempt_id'),
                    'passed': local.get('passed'), 'total': 9,
                    'checks': [{k: c.get(k) for k in (
                        'name', 'path', 'status', 'http_status', 'reason')} for c in checks],
                    'image_id': local.get('image_id'),
                    'acme_e2e': 'NOT_RUN_SANDBOX_SIMULATION_PENDING',
                    'incident_id': None, 'run_id': None, 'glpi_ticket_id': None,
                }
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass
    # Host-executed sandbox qualification is separate from nine anonymous GETs.
    # Never promote CI, a simulator-only response or a stale local receipt to E2E.
    report['acme_sim_e2e'] = {'status': 'NOT_VERIFIED'}
    try:
        sim_path = state_dir / 'acme-sim-e2e.json'
        if sim_path.stat().st_size <= 8192:
            sim = json.loads(sim_path.read_text(encoding='utf-8'))
            when = dt.datetime.fromisoformat(sim['collected_at'].replace('Z', '+00:00'))
            age = (dt.datetime.now(dt.timezone.utc) - when).total_seconds()
            expected = ('simulator', 'core', 'twin', 'policy', 'worker')
            steps = sim.get('stages', {})
            ids = sim.get('ids', {})
            status = sim.get('status')
            safe = (when.tzinfo is not None and 0 <= age <= 900
                    and sim.get('schema') == 'aiops.debian-acme-sim-e2e.v1'
                    and sim.get('tenant_id') == 'ACME-TEST'
                    and sim.get('mode') == 'SIMULATION'
                    and sim.get('approval_issuer') == 'TWIN_ACME_SIMULATED'
                    and sim.get('human_approval_claimed') is False
                    and sim.get('live_effects_allowed') is False
                    and sim.get('real_glpi_writes_allowed') is False
                    and sim.get('docker_mutations') == 0
                    and isinstance(sim.get('attempt_id'), str)
                    and re.fullmatch(r'ACME-SIM-[A-F0-9]{16}', sim['attempt_id'])
                    and isinstance(sim.get('reason'), str)
                    and (sim['reason'] in (
                        'SIMULATED_SANDBOX_ONLY',
                        'SIMULATOR_START_UNQUALIFIED',
                        'INDEPENDENT_READBACK_OR_RESOLUTION_MISMATCH',
                        'WORKER_PRE_RESOLUTION_UNQUALIFIED',
                        'CORE_FINALIZATION_UNQUALIFIED')
                        or re.fullmatch(
                            r'SANDBOX_CAPABILITY_MISSING_(SIMULATOR|CORE|TWIN|POLICY|WORKER)',
                            sim['reason']))
                    and status in ('PASS', 'FAIL', 'BLOCKED')
                    and isinstance(steps, dict) and len(steps) <= 20
                    and all(k in {('capability_' + x) for x in expected} |
                            {('pre_resolution_' + x) for x in expected} |
                            {('post_resolution_' + x) for x in expected} |
                            {'simulator_start', 'worker_no_effect',
                             'core_finalization', 'resolved'}
                            and v in ('PASS', 'FAIL', 'BLOCKED')
                            for k, v in steps.items())
                    and isinstance(ids, dict) and len(ids) <= 5
                    and all(k in ('incident_id','run_id','ticket_id','proposal_id','approval_id')
                            and isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9_-]{3,100}', v)
                            for k, v in ids.items()))
            if safe:
                if status == 'PASS':
                    safe = (sim['reason'] == 'SIMULATED_SANDBOX_ONLY'
                            and all(steps.get('capability_' + x) == 'PASS' for x in expected)
                            and all(steps.get('pre_resolution_' + x) == 'PASS'
                                    and steps.get('post_resolution_' + x) == 'PASS'
                                    for x in ('core','twin','policy','worker'))
                            and steps.get('simulator_start') == 'PASS'
                            and steps.get('worker_no_effect') == 'PASS'
                            and steps.get('core_finalization') == 'PASS'
                            and steps.get('resolved') == 'PASS' and len(ids) == 5)
                if status == 'BLOCKED':
                    safe = not ids and str(sim.get('reason','')).startswith('SANDBOX_CAPABILITY_MISSING_')
                if safe:
                    report['acme_sim_e2e'] = {
                        'collected_at': sim['collected_at'],
                        'attempt_id': sim.get('attempt_id'),
                        'tenant_id': 'ACME-TEST', 'mode': 'SIMULATION',
                        'approval_issuer': 'TWIN_ACME_SIMULATED',
                        'human_approval_claimed': False,
                        'live_effects_allowed': False,
                        'status': status, 'reason': sim.get('reason'),
                        'stages': steps, 'ids': ids,
                        'portal_image_id': report.get('portal', {}).get('image_id'),
                    }
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    # Five-service SHA-pinned upgrade receipt is independent from host E2E.
    # Never infer Docker mutation from CI or stale/unsigned local files.
    report['acme_sandbox_upgrade'] = {'status': 'NOT_VERIFIED'}
    report['acme_sandbox_runtime'] = {'status': 'NOT_VERIFIED', 'services': []}
    try:
        local_path = state_dir / 'acme-sandbox-upgrade.json'
        if local_path.stat().st_size <= 16384:
            local = json.loads(local_path.read_text(encoding='utf-8'))
            when = dt.datetime.fromisoformat(local['collected_at'].replace('Z', '+00:00'))
            age = (dt.datetime.now(dt.timezone.utc) - when).total_seconds()
            images = local.get('images')
            portal_http = local.get('portal_http')
            manifest = json.loads((ROOT / 'deploy/debian-acme-sandbox-release.json').read_text())
            # Historical immutable upgrade evidence remains usable for independent
            # CURRENT Docker readback beyond the 15-minute E2E freshness gate.
            # The age and timestamp stay explicit; this never reruns an upgrade.
            safe = (when.tzinfo is not None and 0 <= age <= 7 * 86400
                    and local.get('schema') == 'aiops.debian-acme-sandbox-upgrade.v1'
                    and manifest.get('enabled') is True
                    and local.get('source_sha') == manifest.get('candidate_sha')
                    and local.get('portal_7777_untouched') is True
                    and local.get('glpi_write') is False
                    and local.get('live_effects_allowed') is False
                    and local.get('status') in ('PASS','FAIL')
                    and type(local.get('docker_container_mutations')) is int
                    and local['docker_container_mutations'] in (0,1)
                    and type(local.get('docker_image_builds')) is int
                    and 0 <= local['docker_image_builds'] <= 5
                    and isinstance(images,list) and len(images) <= 5
                    and all(isinstance(x,dict)
                            and x.get('service') in ('core','twin','policy','worker','simulator')
                            and isinstance(x.get('previous_image_id'),str)
                            and x['previous_image_id'].startswith('sha256:')
                            for x in images))
            if safe and local['status'] == 'PASS':
                safe = (local.get('exit_code') == 0
                        and local['docker_container_mutations'] == 1
                        and local['docker_image_builds'] == 5
                        and len(images) == 5
                        and len({x['service'] for x in images}) == 5
                        and all(x.get('image_changed') is True
                                and x.get('observed_health') == 'healthy'
                                and x.get('http_status') == 200
                                and x.get('json_status') == 'ok'
                                and isinstance(x.get('observed_container_id'),str)
                                and len(x['observed_container_id']) >= 12
                                for x in images)
                        and isinstance(portal_http,dict)
                        and portal_http.get('http_status') == 200
                        and portal_http.get('json_status') == 'ok'
                        and portal_http.get('external_port') == 7777
                        and local.get('rollback_status') == 'NOT_REQUIRED'
                        and local.get('pg16_scratch_restore') == 'PASS'
                        and isinstance(local.get('pg16_backup_sha256'),str)
                        and re.fullmatch(r'[0-9a-f]{64}',local['pg16_backup_sha256']))
            if safe:
                report['acme_sandbox_upgrade'] = {
                    'collected_at': local['collected_at'],
                    'historical_receipt': age > 900,
                    'status': local['status'], 'source_sha': local['source_sha'],
                    'stable_checkout_sha': local.get('stable_checkout_sha'),
                    'dev_checkout_sha': local.get('dev_checkout_sha'),
                    'docker_container_mutations': local['docker_container_mutations'],
                    'docker_image_builds': local['docker_image_builds'],
                    'rollback_status': local.get('rollback_status'),
                    'pg16_backup_sha256': local.get('pg16_backup_sha256'),
                    'pg16_scratch_restore': local.get('pg16_scratch_restore'),
                    'portal_http': portal_http,
                    'images': [{k:x.get(k) for k in (
                        'service','previous_image_id','observed_image_id',
                        'observed_container_id','observed_health',
                        'image_changed','http_status','json_status')} for x in images],
                }
                if local['status'] == 'PASS':
                    report['acme_sandbox_runtime'] = acme_runtime_snapshot(poller, images)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    report['acme_sandbox_verdict'] = (
        'GO_SIMULATED_SANDBOX_ONLY'
        if report['acme_sim_e2e'].get('status') == 'PASS'
        and report['acme_sandbox_upgrade'].get('status') == 'PASS'
        and report['acme_sandbox_runtime'].get('status') == 'PASS'
        else 'NO_GO_NOT_RUNTIME_VERIFIED')
    report['host_playwright'] = host_playwright_receipt(
        state_dir, report.get('stable_checkout_sha'),
        report.get('portal', {}).get('image_id'))
    report['release_stable'] = 'NO_GO'
    report['execution'] = ('POLLER_DEPLOY_RECEIPT_AND_READONLY_VERIFICATION'
                           if report['deployment_preflight']['deployment_executed']
                           else 'POLLER_ENTRYPOINT_READONLY_PREFLIGHT')
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
