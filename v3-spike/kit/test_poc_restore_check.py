import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from poc_restore_check import read_archive, verify_restore

NAME = 'poc-pg-20261128T000000000000Z.dump'
RAW = b'PGDMP synthetic fixture'
SHA = hashlib.sha256(RAW).hexdigest()
SOURCE = 'a' * 64
DEST = 'b' * 64
IMAGE = 'sha256:' + 'c' * 64
TOKEN = 'd' * 32
RESOURCE = 'aiops-v3-restore-' + TOKEN
LABEL = 'aiops.v3.restore.check'


class FakeLifecycle:
    project = 'aiops-v3-poc-fixture'

    def __init__(self, root):
        self.root = root
        self.calls = []
        self.unsafe = False
        self.nonempty = False
        self.bad_owner = False
        self.restore_fail = False
        self.installed_called = False

    def installed(self):
        self.installed_called = True

    def compose(self, args, **kwargs):
        assert args == ['ps', '-q', 'postgres']
        self.calls.append(('compose', *args))
        return subprocess.CompletedProcess(args, 0, SOURCE + '\n')

    def command(self, args, *, input, capture_output, timeout):
        self.calls.append(tuple(args))
        cmd = args[1:]
        if cmd[:2] == ['container', 'inspect']:
            if cmd[2] == SOURCE:
                val = [{'Id': SOURCE, 'Image': IMAGE, 'Config': {'Labels': {
                    'com.docker.compose.project': self.project, 'com.docker.compose.service': 'postgres'}}}]
            else:
                assert cmd[2] == DEST
                val = [{'Id': DEST, 'Image': IMAGE, 'Config': {'Labels': {LABEL: TOKEN}},
                        'HostConfig': {'NetworkMode': 'host' if self.unsafe else 'none', 'PortBindings': {}, 'Privileged': False},
                        'Mounts': [{'Type': 'volume', 'Name': RESOURCE, 'Destination': '/var/lib/postgresql/data'}]}]
                if self.bad_owner:
                    val[0]['Config']['Labels'][LABEL] = 'foreign'
            out = json.dumps(val).encode()
        elif cmd[:2] in (['volume', 'ls'], ['container', 'ls']):
            out = b''
        elif cmd[:2] == ['volume', 'create']:
            out = (RESOURCE + '\n').encode()
        elif cmd[:2] == ['volume', 'inspect']:
            out = json.dumps([{'Name': RESOURCE, 'Driver': 'local', 'Options': None,
                               'Labels': {LABEL: TOKEN}, 'Mountpoint': str(self.root / 'docker-data')}]).encode()
        elif cmd[0] == 'create':
            assert '--network' in cmd and cmd[cmd.index('--network')+1] == 'none'
            assert cmd[-1] == IMAGE
            out = DEST.encode()
        elif cmd[0] in ('start', 'rm'):
            assert cmd[-1] == DEST
            out = b''
        elif cmd[:2] == ['volume', 'rm']:
            assert cmd[-1] == RESOURCE
            out = b''
        elif cmd[0] == 'exec':
            assert DEST in cmd and SOURCE not in cmd
            if 'pg_restore' in cmd:
                assert input == RAW
                if self.restore_fail and '--single-transaction' in cmd:
                    raise subprocess.CalledProcessError(1, args)
            if 'psql' in cmd:
                out = b'1\n' if self.nonempty else b'0\n'
            else:
                out = b''
        else:
            raise AssertionError(cmd)
        return subprocess.CompletedProcess(args, 0, stdout=out)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'backup').mkdir(mode=0o700)
        (self.root / 'docker-data').mkdir()
        self.archive = self.root / 'backup' / NAME
        self.archive.write_bytes(RAW)
        self.archive.chmod(0o600)
        self.ctl = FakeLifecycle(self.root)
        self.snap = {'tables': {'runs': {'rows': 1}}, 'schema_sha256': 'fixture'}

    def restore(self):
        with patch('poc_restore_check.secrets.token_hex', side_effect=[TOKEN, 'e' * 48]):
            return verify_restore(self.ctl, NAME, SHA, lambda q: self.snap, sleep=lambda _: None)

    def test_archive_roundtrip(self):
        self.assertEqual(read_archive(self.root, NAME, SHA), RAW)

    def test_bad_digest_and_traversal(self):
        for name, digest in [(NAME, '0' * 64), ('../' + NAME, SHA), (NAME, 'bad')]:
            with self.subTest(name=name, digest=digest), self.assertRaises(ValueError):
                read_archive(self.root, name, digest)

    def test_public_archive_rejected(self):
        self.archive.chmod(0o644)
        with self.assertRaises(ValueError):
            read_archive(self.root, NAME, SHA)

    def test_symlink_and_hardlink_rejected(self):
        other = self.root / 'other'
        self.archive.rename(other)
        self.archive.symlink_to(other)
        with self.assertRaises(OSError):
            read_archive(self.root, NAME, SHA)
        self.archive.unlink()
        self.archive.hardlink_to(other)
        with self.assertRaises(ValueError):
            read_archive(self.root, NAME, SHA)

    def test_nominal_restore_checks_only_destination(self):
        report = self.restore()
        self.assertTrue(self.ctl.installed_called)
        self.assertEqual(report['result'], 'PASS')
        self.assertEqual(report['snapshot'], self.snap)
        self.assertEqual(report['source_snapshot_match'], 'NOT_RUN')
        self.assertFalse(report['active_database_restored'])
        self.assertIn(('docker', 'rm', '-f', DEST), self.ctl.calls)
        self.assertIn(('docker', 'volume', 'rm', RESOURCE), self.ctl.calls)
        self.assertFalse((self.root / (RESOURCE + '.env')).exists())

    def test_unsafe_network_never_starts(self):
        self.ctl.unsafe = True
        with self.assertRaisesRegex(ValueError, 'unsafe restore container'):
            self.restore()
        self.assertNotIn(('docker', 'start', DEST), self.ctl.calls)
        self.assertIn(('docker', 'rm', '-f', DEST), self.ctl.calls)

    def test_foreign_container_never_started_or_removed(self):
        self.ctl.bad_owner = True
        with self.assertRaisesRegex(ValueError, 'ownership'):
            self.restore()
        self.assertNotIn(('docker', 'start', DEST), self.ctl.calls)
        self.assertNotIn(('docker', 'rm', '-f', DEST), self.ctl.calls)

    def test_nonempty_destination_never_restored(self):
        self.ctl.nonempty = True
        with self.assertRaisesRegex(ValueError, 'not empty'):
            self.restore()
        self.assertFalse(any('pg_restore' in call for call in self.ctl.calls))

    def test_restore_failure_cleans_owned_resources(self):
        self.ctl.restore_fail = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.restore()
        self.assertIn(('docker', 'rm', '-f', DEST), self.ctl.calls)
        self.assertIn(('docker', 'volume', 'rm', RESOURCE), self.ctl.calls)
        self.assertFalse((self.root / (RESOURCE + '.env')).exists())

    def test_bad_archive_precedes_docker(self):
        self.archive.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.restore()
        self.assertEqual(self.ctl.calls, [])


if __name__ == '__main__':
    unittest.main()
