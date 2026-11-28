"""Control-flow tests; actual PostgreSQL is exercised by the rootless CI job."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from poc_restore_smoke import prove

SNAP = {'tables': {'runs': {'rows': 1, 'sha256': 'fixture'}}, 'schema_sha256': 'fixture'}
SHA = 'a' * 64


class Fake:
    root = Path('/tmp/fixture')
    orchestration = False

    def __init__(self):
        self.events = []
        self.running_writer = False

    def health(self):
        self.events.append('health')

    def start(self):
        self.events.append('start')

    def compose(self, args, **kwargs):
        self.events.append(tuple(args))
        if args[0] == 'ps':
            return SimpleNamespace(stdout='container' if self.running_writer else '')
        return SimpleNamespace(stdout=b'')

    def backup(self):
        self.events.append('backup')
        return {'result': 'PASS', 'restore_tested': False,
                'archive': str(self.root / 'backup' / 'poc-pg-fixture.dump'),
                'sha256': SHA, 'bytes': 12}


class RestoreSmokeTests(unittest.TestCase):
    def setUp(self):
        self.ctl = Fake()
        self.snapshots = [SNAP, SNAP]
        self.receipt = {'result': 'PASS', 'snapshot': SNAP, 'backup_sha256': SHA,
                        'backup_bytes': 12, 'active_database_restored': False,
                        'production_authorized': False}

    def run_proof(self):
        return prove(self.ctl, project_snapshot=lambda query: self.snapshots.pop(0),
                     restore=lambda *args: self.receipt)

    def test_nominal(self):
        report = self.run_proof()
        self.assertEqual(report['source_snapshot_match'], 'PASS')
        self.assertTrue(report['source_unchanged'])
        self.assertTrue(report['writers_resumed'])
        self.assertEqual(self.ctl.events[-2:], ['start', 'health'])

    def test_changed_source_fails_and_resumes(self):
        self.snapshots[1] = {}
        with self.assertRaisesRegex(ValueError, 'source changed'):
            self.run_proof()
        self.assertEqual(self.ctl.events[-2:], ['start', 'health'])

    def test_changed_restore_fails_and_resumes(self):
        self.receipt['snapshot'] = {}
        with self.assertRaisesRegex(ValueError, 'restored rows or schema differ'):
            self.run_proof()
        self.assertEqual(self.ctl.events[-2:], ['start', 'health'])

    def test_wrong_archive_fails(self):
        self.receipt['backup_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'archive identity'):
            self.run_proof()
        self.assertEqual(self.ctl.events[-2:], ['start', 'health'])

    def test_writer_running_refuses_backup(self):
        self.ctl.running_writer = True
        with self.assertRaisesRegex(ValueError, 'writer still running'):
            self.run_proof()
        self.assertNotIn('backup', self.ctl.events)
        self.assertEqual(self.ctl.events[-2:], ['start', 'health'])

    def test_orchestration_rejected_without_mutation(self):
        self.ctl.orchestration = True
        with self.assertRaises(ValueError):
            self.run_proof()
        self.assertEqual(self.ctl.events, [])


if __name__ == '__main__':
    unittest.main()
