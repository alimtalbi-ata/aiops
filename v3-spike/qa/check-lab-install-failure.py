"""LAB failure diagnostics: fixture contract and isolated CI port-conflict campaign."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import socket
import stat
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path('/tmp/aiops-v3-rootless-ci')
SERVICES = {'postgres', 'core', 'twin', 'evidence', 'policy', 'temporal-postgres', 'temporal', 'worker', 'gamma'}
CATEGORIES = {'PERMISSION_DENIED', 'NO_SPACE', 'POSTGRES_FATAL', 'POSTGRES_ERROR'}
STATES = {'created', 'running', 'paused', 'restarting', 'removing', 'exited', 'dead', 'UNAVAILABLE'}
HEALTH = {'starting', 'healthy', 'unhealthy', 'UNAVAILABLE', None}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify_report(state):
    path = state / 'failure-diagnostics.json'
    require(path.is_file() and not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o600, 'private diagnostic receipt required')
    report = json.loads(path.read_text())
    require(set(report) == {'classification', 'result', 'slot', 'error_type', 'services', 'production_authorized'}, 'unexpected report fields')
    require(report['classification'] == 'V3_LAB_INSTALL_FAILURE_DIAGNOSTICS' and report['result'] == 'FAIL' and report['slot'] == 1 and report['production_authorized'] is False, 'invalid report identity')
    require(report['error_type'] == 'CalledProcessError' and set(report['services']) == SERVICES, 'invalid error or services')
    for name, row in report['services'].items():
        require(set(row) == {'state', 'exit_code', 'health', 'log_categories'}, 'unexpected service fields')
        require(row['state'] in STATES and row['health'] in HEALTH and (row['exit_code'] is None or type(row['exit_code']) is int and 0 <= row['exit_code'] <= 999), 'invalid service state')
        require(isinstance(row['log_categories'], list) and set(row['log_categories']) <= CATEGORIES and (name in {'postgres', 'temporal-postgres'} or not row['log_categories']), 'unexpected log categories')
    require(not (state / 'install-report.json').exists(), 'failed installation reported success')
    return report


def fixture(installer):
    diagnostic = runpy.run_path(str(installer))['failure_diagnostics']
    canary = 'SYNTHETIC-CREDENTIAL-MUST-NOT-ESCAPE'
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp)
        def capture(args, **kwargs):
            if 'ps' in args:
                service = args[-1]
                if service == 'worker':
                    raise subprocess.TimeoutExpired(args, 10)
                data = b'a' * 64 if service != 'gamma' else canary.encode()
            else:
                data = ('FATAL: permission denied; ' + canary).encode()
            return subprocess.CompletedProcess(args, 0, stdout=data, stderr=canary.encode())
        with patch.object(subprocess, 'run', side_effect=capture), patch.object(subprocess, 'check_output', return_value=b'"exited" 1 null'), contextlib.redirect_stdout(io.StringIO()) as out:
            diagnostic(['fixture'], {}, state, state, '1', subprocess.CalledProcessError(1, ['fixture']))
        report = verify_report(state)
        require(canary not in (state / 'failure-diagnostics.json').read_text() + out.getvalue(), 'fixture canary leaked')
        require(report['services']['postgres']['log_categories'] == ['PERMISSION_DENIED', 'POSTGRES_FATAL'], 'known categories missing')
        require(all(report['services'][name]['state'] == 'UNAVAILABLE' for name in ('worker', 'gamma')), 'malformed or timed out response trusted')
    print('PASS diagnostic fixture; subprocess mocked, no Docker runtime')


def runtime(bundle):
    require(os.getenv('GITHUB_ACTIONS') == 'true' and os.getuid() != 0 and ROOT.resolve() == ROOT and ROOT.stat().st_uid == os.getuid() and not ROOT.stat().st_mode & 0o077, 'dedicated CI only')
    require(bundle == ROOT / 'install-1' / 'bundle' and bundle.resolve() == bundle, 'wrong bundle')
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, timeout=30, stderr=subprocess.PIPE).strip()
    require('name=rootless' in docker('info', '--format', '{{json .SecurityOptions}}') and docker('info', '--format', '{{.DockerRootDir}}') == str(ROOT / 'docker-data'), 'wrong daemon')
    state = bundle.parent
    project = 'v3-lab-install-1'
    def empty_project():
        for kind in ('container', 'volume', 'network'):
            require(not docker(kind, 'ls', '-aq' if kind == 'container' else '-q', '--filter', 'label=com.docker.compose.project=' + project), 'project resources remain')
    empty_project()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.bind(('127.0.0.1', 18080))
        blocker.listen(1)
        child = subprocess.run([sys.executable, str(bundle / 'install-ci.py'), str(bundle), '1'], cwd=bundle, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
        require(child.returncode != 0, 'expected installation failure')
        report = verify_report(state)
        require(any(row['state'] != 'UNAVAILABLE' for row in report['services'].values()), 'no container state captured')
        require(not (state / 'poc.env').exists(), 'secret file retained')
        empty_project()
    print(json.dumps({'classification': 'V3_LAB_FAILURE_INJECTION', 'result': 'PASS', 'injection': 'loopback port occupied', 'install_exit_nonzero': True, 'cleanup_verified': True, 'production_authorized': False}, sort_keys=True))


if __name__ == '__main__':
    mode, arg = sys.argv[1:]
    if mode == 'fixture':
        fixture(Path(arg))
    elif mode == 'runtime':
        runtime(Path(arg))
    else:
        raise ValueError('expected fixture or runtime')
