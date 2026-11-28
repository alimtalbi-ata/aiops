"""Verify a trusted POC PostgreSQL backup in a disposable, disconnected database.

Never restores into the active database. This is a bounded logical restore
check, not a coordinated backup or disaster recovery procedure.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time

MAX_BYTES = 32 * 1024**2
HERE = Path(__file__).resolve().parent


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read_archive(root, name, expected):
    require(isinstance(name, str) and re.fullmatch(r'poc-pg-[0-9]{8}T[0-9]{12}Z\.dump', name),
            'invalid backup filename')
    require(isinstance(expected, str) and re.fullmatch(r'[a-f0-9]{64}', expected),
            'expected SHA-256 required')
    root = Path(root)
    directory = root / 'backup'
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    fd = os.open(directory, flags)
    try:
        info = os.fstat(fd)
        require(info.st_uid == os.getuid() and not info.st_mode & 0o077
                and directory.resolve(strict=True) == directory,
                'private canonical backup directory required')
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                    and info.st_nlink == 1 and not info.st_mode & 0o077
                    and 0 < info.st_size <= MAX_BYTES, 'invalid private backup archive')
            raw = stream.read(MAX_BYTES + 1)
            require(len(raw) == info.st_size and raw.startswith(b'PGDMP'), 'invalid custom archive')
    finally:
        os.close(fd)
    require(hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected), 'backup digest mismatch')
    return raw


def verify_restore(ctl, name, expected, snapshot, *, sleep=time.sleep):
    """Use Lifecycle's rootless preflight and existing E17 schema snapshot."""
    ctl.installed()
    raw = read_archive(ctl.root, name, expected)

    def docker(*args, data=None, timeout=30):
        return ctl.command(['docker', *args], input=data, capture_output=True,
                           timeout=timeout).stdout

    def inspect(kind, identity):
        rows = json.loads(docker(kind, 'inspect', identity))
        require(isinstance(rows, list) and len(rows) == 1, 'ambiguous Docker identity')
        return rows[0]

    source = ctl.compose(['ps', '-q', 'postgres'], capture_output=True, text=True, timeout=20).stdout.strip()
    require(re.fullmatch(r'[a-f0-9]{12,64}', source), 'missing source PostgreSQL')
    info = inspect('container', source)
    labels = info['Config']['Labels']
    image = info['Image']
    require(info['Id'].startswith(source) and labels.get('com.docker.compose.project') == ctl.project
            and labels.get('com.docker.compose.service') == 'postgres'
            and re.fullmatch(r'sha256:[a-f0-9]{64}', image), 'unverified source PostgreSQL')
    token = secrets.token_hex(16)
    resource = 'aiops-v3-restore-' + token
    label = 'aiops.v3.restore.check'
    require(resource not in docker('volume', 'ls', '--format', '{{.Name}}').decode().splitlines()
            and resource not in docker('container', 'ls', '-a', '--format', '{{.Names}}').decode().splitlines(),
            'restore destination exists')
    volume = False
    cid = None
    envfile = ctl.root / (resource + '.env')
    fd = os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('POSTGRES_USER=aiops\nPOSTGRES_DB=aiops\nPOSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n')
        require(docker('volume', 'create', '--label', label + '=' + token, resource).decode().strip() == resource,
                'invalid volume creation receipt')
        vol = inspect('volume', resource)
        require(vol['Name'] == resource and vol['Driver'] == 'local' and not vol.get('Options')
                and vol['Labels'].get(label) == token
                and Path(vol['Mountpoint']).resolve(strict=True).is_relative_to(ctl.root),
                'unverified restore volume')
        volume = True
        candidate = docker('create', '--pull', 'never', '--network', 'none', '--name', resource,
                           '--label', label + '=' + token, '--security-opt', 'no-new-privileges',
                           '--env-file', str(envfile), '--mount',
                           f'type=volume,source={resource},target=/var/lib/postgresql/data', image).decode().strip()
        require(re.fullmatch(r'[a-f0-9]{64}', candidate) and not candidate.startswith(source),
                'invalid restore container identity')
        dest = inspect('container', candidate)
        require(dest['Id'] == candidate and dest['Config']['Labels'].get(label) == token,
                'unverified restore container ownership')
        cid = candidate
        host = dest['HostConfig']
        mounts = dest['Mounts']
        require(dest['Image'] == image and host['NetworkMode'] == 'none' and not host.get('PortBindings')
                and not host.get('Privileged') and len(mounts) == 1
                and mounts[0]['Type'] == 'volume' and mounts[0]['Name'] == resource
                and mounts[0]['Destination'] == '/var/lib/postgresql/data', 'unsafe restore container')
        docker('start', cid)
        for _ in range(60):
            try:
                docker('exec', cid, 'pg_isready', '-h', '127.0.0.1', '-U', 'aiops', '-d', 'aiops', timeout=5)
                break
            except subprocess.CalledProcessError:
                sleep(1)
        else:
            raise ValueError('restore database not ready')

        def query(sql):
            return docker('exec', '-i', cid, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
                          '-U', 'aiops', '-d', 'aiops', data=("SET TIME ZONE 'UTC';\n" + sql).encode())

        require(query("SELECT count(*) FROM pg_namespace WHERE nspname='aiops';").strip() == b'0',
                'restore database not empty')
        docker('exec', '-i', cid, 'pg_restore', '--list', data=raw, timeout=60)
        docker('exec', '-i', cid, 'pg_restore', '--exit-on-error', '--single-transaction',
               '--no-owner', '--no-privileges', '-U', 'aiops', '-d', 'aiops', data=raw, timeout=300)
        result = snapshot(query)
        return {'result': 'PASS', 'scope': 'POSTGRES_LOGICAL_RESTORE_CHECK_ONLY',
                'backup_sha256': expected, 'backup_bytes': len(raw), 'snapshot': result,
                'source_snapshot_match': 'NOT_RUN', 'active_database_restored': False,
                'temporal_restore': 'NOT_RUN', 'collector_authority_restore': 'NOT_RUN',
                'production_authorized': False}
    finally:
        # Never delete a container or volume without verified ownership. An
        # ambiguous creation result can leave an isolated resource for inspection.
        try:
            if cid is not None:
                docker('rm', '-f', cid)
        finally:
            try:
                if volume:
                    docker('volume', 'rm', resource)
            finally:
                envfile.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', help='backup basename inside V3_ROOT/backup')
    parser.add_argument('sha256', help='digest from the trusted backup receipt')
    parser.add_argument('--root', default=os.environ.get('V3_ROOT', '/srv/aiops-v3'))
    args = parser.parse_args(argv)
    from pocctl import Lifecycle
    sys.path.insert(0, str(HERE / 'release-lab'))
    from e17_pg_restore import snapshot
    try:
        report = verify_restore(Lifecycle(args.root), args.archive, args.sha256, snapshot)
        print(json.dumps(report, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print('POC restore check failed: ' + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
