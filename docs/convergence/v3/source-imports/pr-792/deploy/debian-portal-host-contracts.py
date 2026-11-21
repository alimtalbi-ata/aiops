#!/usr/bin/env python3
"""Nine anonymous, non-mutating portal HTTP contracts on the real Debian :7777.

No bearer, cookie, GLPI writes, actor impersonation, redirects, external URLs,
or positive human ALLOW. This is not the ACME Incident-to-Resolution E2E.
"""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.request

STATE = Path('/home/aiops/.local/state/aiops-debian-agent')
ORIGIN = 'http://127.0.0.1:7777'
CASES = (
    ('health', '/health', 'health'),
    ('shell', '/', 'html'),
    ('itsm_shell', '/itsm', 'html'),
    ('oidc_session', '/api/portal/session', 'denied'),
    ('bootstrap', '/api/portal/bootstrap', 'denied'),
    ('components', '/api/portal/components', 'denied'),
    ('glpi_authority', '/api/portal/itsm', 'denied'),
    ('noc_runtime', '/api/noc/runtime-state', 'denied'),
    ('noc_correlation', '/api/noc/correlation', 'denied'),
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def qualify(case, opener):
    name, path, kind = case
    result = {'name': name, 'path': path, 'status': 'FAIL', 'http_status': None,
              'reason': 'NO_RESPONSE'}
    request = urllib.request.Request(ORIGIN + path, method='GET',
                                     headers={'Accept': 'application/json, text/html',
                                              'Cache-Control': 'no-store'})
    try:
        try:
            response = opener.open(request, timeout=4)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            code = response.status
            headers = response.headers
            raw = response.read(16385)
        result['http_status'] = code
        if len(raw) > 16384:
            result['reason'] = 'RESPONSE_TOO_LARGE'
            return result
        if 'no-store' not in headers.get('Cache-Control', '').lower():
            result['reason'] = 'CACHE_NOT_DISABLED'
            return result
        if headers.get('X-Content-Type-Options', '').lower() != 'nosniff':
            result['reason'] = 'NOSNIFF_MISSING'
            return result
        if kind == 'html':
            good = code == 200 and 'text/html' in headers.get('Content-Type', '').lower()
            result['reason'] = 'HTML_SHELL_ONLY' if good else 'HTML_CONTRACT_MISMATCH'
        else:
            try:
                obj = json.loads(raw.decode('utf-8'))
            except (UnicodeDecodeError, ValueError):
                result['reason'] = 'JSON_INVALID'
                return result
            if not isinstance(obj, dict):
                result['reason'] = 'JSON_NOT_OBJECT'
                return result
            if kind == 'health':
                good = (code == 200 and obj.get('status') == 'ok' and
                        type(obj.get('external_port')) is int and obj['external_port'] == 7777)
                result['reason'] = 'STRICT_7777_HEALTH' if good else 'HEALTH_CONTRACT_MISMATCH'
            else:
                # 503 is a legitimate fail-closed result when authority is absent.
                good = (code in (401, 403, 503) and
                        obj.get('state') not in ('OK', 'ALLOW', 'AUTHORIZED') and
                        obj.get('human_allow') is not True and
                        obj.get('live_remediation_authorized') is not True and
                        (not isinstance(obj.get('human_authority'), dict) or
                         obj['human_authority'].get('human_allow') is not True))
                result['reason'] = 'AUTHORITY_DENIED_OR_UNKNOWN' if good else 'AUTHORITY_NOT_FAIL_CLOSED'
        result['status'] = 'PASS' if good else 'FAIL'
    except (OSError, ValueError, TimeoutError):
        result['reason'] = 'NETWORK_OR_HTTP_ERROR'
    return result


def atomic_receipt(path, obj):
    fd, tmp = tempfile.mkstemp(prefix='.portal-contract-', dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(obj, f, sort_keys=True)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    now = dt.datetime.now(dt.timezone.utc)
    attempt_id = 'ACME-READONLY-' + now.strftime('%Y%m%dT%H%M%SZ')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    results = [qualify(c, opener) for c in CASES]
    passed = sum(r['status'] == 'PASS' for r in results)
    # Docker inspection is read-only. Never expose env/labels or raw API responses.
    try:
        inspect = subprocess.run(['docker', 'inspect', 'aiops2-rebuild-portal',
                                  '--format', '{{.Image}}|{{.Id}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}'],
                                 capture_output=True, text=True, timeout=8, check=False)
        parts = inspect.stdout.strip().split('|') if inspect.returncode == 0 else []
        image, container, health = parts if len(parts) == 3 else (None, None, None)
        if not (image and image.startswith('sha256:') and len(image) == 71):
            image = None
        if not (container and len(container) == 64):
            container = None
    except (OSError, subprocess.TimeoutExpired):
        image, container, health = None, None, None
    receipt = {
        'schema': 'aiops.debian-portal-anonymous-nine-contracts.v1',
        'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'attempt_id': attempt_id, 'scope': '127.0.0.1:7777',
        'image_id': image, 'container_id': container, 'container_health': health,
        'checks': results, 'passed': passed, 'total': len(CASES),
        'verdict': 'PASS_READONLY_ONLY' if passed == len(CASES) and health == 'healthy' and image else 'FAIL',
        'incident_id': None, 'run_id': None, 'glpi_ticket_id': None,
        'acme_e2e': 'BLOCKED_NO_INDEPENDENT_HUMAN_GLPI_IDP_AUTHORITY',
        'human_allow': False, 'worker_effects': 0, 'glpi_writes': 0,
    }
    atomic_receipt(STATE / 'portal-host-contracts.json', receipt)
    print('PORTAL_NINE_READONLY=%d/%d verdict=%s' %
          (passed, len(CASES), receipt['verdict']))
    return 0 if receipt['verdict'] == 'PASS_READONLY_ONLY' else 78


if __name__ == '__main__':
    raise SystemExit(main())
