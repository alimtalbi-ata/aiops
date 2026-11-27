"""Executable source-built POC lifecycle, on a dedicated rootless daemon only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

from rootless_preflight import source_daemon_preflight, validate_root

HERE = Path(__file__).resolve().parent
BASE = ('postgres', 'core', 'twin', 'evidence', 'policy')
ORCHESTRATION = ('temporal-postgres', 'temporal', 'worker', 'temporal-ui')
GUARD_DIRS = ('collector-control', 'collector-authority', 'collector-witness')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def private(path, directory=False):
    st = path.lstat()
    require((stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode))
            and st.st_uid == os.getuid() and not st.st_mode & 0o077
            and (directory or st.st_nlink == 1) and path.resolve(strict=True) == path,
            'private canonical POC path required')


class Lifecycle:
    def __init__(self, root, orchestration=False, *, env=None, run=subprocess.run,
                 preflight=source_daemon_preflight):
        self.root = validate_root(root)
        private(self.root, directory=True)
        self.env = {k: v for k, v in (os.environ if env is None else env).items()
                    if not k.startswith('COMPOSE_') and k not in ('V3_DB_PASSWORD', 'V3_LAB_TOKEN')}
        self.env['V3_ROOT'] = str(self.root)
        preflight(self.root, env=self.env)
        self.run = run
        self.orchestration = orchestration
        self.project = 'aiops-v3-poc-' + hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
        self.envfile = self.root / 'poc.env'
        self.base = ['docker', 'compose', '--project-name', self.project,
                     '--env-file', str(self.envfile), '-f', str(HERE / 'compose.poc-source.yml')]

    def command(self, args, **kwargs):
        return self.run(args, env=self.env, cwd=HERE, check=True, **kwargs)

    def installed(self):
        private(self.envfile)
        require(re.fullmatch(r'V3_DB_PASSWORD=[a-f0-9]{48}\nV3_LAB_TOKEN=[a-f0-9]{64}\n',
                             self.envfile.read_text()), 'invalid POC credentials')

    def compose(self, args, *, all_profiles=False, **kwargs):
        self.installed()
        profile = ['--profile', 'orchestration'] if self.orchestration or all_profiles else []
        return self.command(self.base + profile + args, **kwargs)

    def install(self):
        require(not any((self.root / name).exists() or (self.root / name).is_symlink()
                        for name in ('poc.env', 'data', 'backup', *GUARD_DIRS)),
                'install requires a fresh dedicated root; use start for existing data')
        if self.orchestration:
            self.env['COMPOSE_PROFILES'] = 'orchestration'
        try:
            self.command(['bash', str(HERE / 'poc-start.sh')], timeout=900)
        finally:
            self.env.pop('COMPOSE_PROFILES', None)
        self.installed()

    def start(self):
        self.compose(['up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '300'],
                     timeout=360)

    def stop(self):
        self.compose(['stop', '--timeout', '20'], all_profiles=True, timeout=180)

    def health(self):
        states = {}
        for name in BASE + (ORCHESTRATION if self.orchestration else ()):
            result = self.compose(['ps', '-q', name], capture_output=True, text=True, timeout=20)
            cid = result.stdout.strip()
            require(re.fullmatch(r'[a-f0-9]{12,64}', cid), 'missing service: ' + name)
            raw = self.command(['docker', 'inspect', '--type', 'container', '--format',
                '{{json .State}} {{json (index .Config.Labels "com.docker.compose.project")}}', cid],
                capture_output=True, text=True, timeout=20).stdout.strip()
            state_raw, project_raw = raw.rsplit(' ', 1)
            state = json.loads(state_raw)
            require(json.loads(project_raw) == self.project and state.get('Status') == 'running',
                    'service not running: ' + name)
            health = state.get('Health', {}).get('Status')
            require(health == 'healthy' or (name == 'temporal-ui' and health is None),
                    'service not healthy: ' + name)
            states[name] = health or 'RUNNING_NO_HEALTHCHECK'
        return {'result': 'PASS', 'scope': 'SOURCE_SERVICES_ONLY', 'services': states,
                'gamma_qualified': False, 'production_authorized': False}

    def backup(self):
        self.installed()
        directory = self.root / 'backup'
        directory.mkdir(mode=0o700, exist_ok=True)
        private(directory, directory=True)
        fd, tmp = tempfile.mkstemp(prefix='.pg-', suffix='.partial', dir=directory)
        temporary = Path(tmp)
        destination = directory / ('poc-pg-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.dump')
        try:
            with os.fdopen(fd, 'wb') as out:
                self.compose(['exec', '-T', 'postgres', 'pg_dump', '-U', 'aiops', '-Fc', 'aiops'],
                             stdout=out, stderr=subprocess.PIPE, timeout=300)
                out.flush()
                os.fsync(out.fileno())
            require(temporary.stat().st_size > 0, 'empty archive')
            with temporary.open('rb') as inp:
                self.compose(['exec', '-T', 'postgres', 'pg_restore', '--list'],
                             stdin=inp, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)
            with temporary.open('rb') as inp:
                digest = hashlib.file_digest(inp, 'sha256').hexdigest()
            os.link(temporary, destination)
            return {'result': 'PASS', 'scope': 'POSTGRES_LOGICAL_ONLY', 'archive': str(destination),
                    'sha256': digest, 'bytes': destination.stat().st_size,
                    'restore_tested': False, 'production_authorized': False}
        finally:
            temporary.unlink(missing_ok=True)

    def gamma(self, provision=False, port=None):
        self.installed()
        args = [sys.executable, str(HERE / 'poc-gamma.py')]
        if provision:
            args.append('--provision-collector')
        elif any((self.root / n).exists() or (self.root / n).is_symlink() for n in GUARD_DIRS):
            require(type(port) is int and 1024 <= port <= 65535 and port not in (7770, 7777, 7790),
                    'explicit guarded GAMMA port required')
            self.env['V3_GUARDED_GAMMA_PORT'] = str(port)
            args.append('--guarded-collector')
        self.command(args)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'start', 'stop', 'health', 'backup', 'provision', 'gamma'))
    parser.add_argument('--root', default=os.environ.get('V3_ROOT', '/srv/aiops-v3'))
    parser.add_argument('--orchestration', action='store_true')
    parser.add_argument('--port', type=int)
    args = parser.parse_args(argv)
    try:
        ctl = Lifecycle(args.root, args.orchestration)
        if args.action in ('provision', 'gamma'):
            ctl.gamma(provision=args.action == 'provision', port=args.port)
        else:
            report = getattr(ctl, args.action)()
            if report is not None:
                print(json.dumps(report, sort_keys=True))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Never emit subprocess captured output or credentials.
        print('POC command failed: ' + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
