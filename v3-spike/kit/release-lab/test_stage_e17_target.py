"""Offline regression for the E17 image's explicit source dependency inventory."""
import contextlib
import hashlib
import io
from pathlib import Path
import runpy
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
STAGER = runpy.run_path(str(HERE / 'stage-e17-target.py'))
WORKER = '127.0.0.1:15080/aiops-v3/worker@sha256:' + 'a' * 64
PATHS = {Path('kit') / n for n in STAGER['KIT']} | {
    Path('vertical') / (n + '.py') for n in STAGER['VERTICAL']}


def stage(source, destination, worker=WORKER):
    with contextlib.redirect_stdout(io.StringIO()):
        return STAGER['stage'](source, destination, worker)


class StageTargetTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root / 'source'
        self.out = self.root / 'output'
        for path in PATHS:
            p = self.source / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('# synthetic fixture\n')
        for name in ('core_ingest', 'core_read', 'ingestion_store'):
            (self.source / 'vertical' / (name + '.py')).write_text(
                'from bounded_http_transport import get_json\n')

    def assert_inventory(self, source, report):
        files = {p.relative_to(self.out) for p in self.out.rglob('*') if p.is_file()}
        self.assertEqual(files, PATHS | {Path('Dockerfile')})
        self.assertEqual(len(PATHS), 30)
        self.assertIn(Path('vertical/bounded_http_transport.py'), PATHS)
        self.assertEqual(set(report['files']), {p.as_posix() for p in files})
        for path in files:
            raw = (self.out / path).read_bytes()
            self.assertEqual(report['files'][path.as_posix()], hashlib.sha256(raw).hexdigest())
            if path in PATHS:
                self.assertEqual(raw, (source / path).read_bytes())
        self.assertEqual(report['worker_base'], WORKER)
        self.assertFalse(report['production_authorized'])
        self.assertEqual(report['runtime'], 'NOT_RUN')

    def test_inventory_and_hashes(self):
        (self.source / 'vertical/unrelated.py').write_text('# not shipped\n')
        self.assert_inventory(self.source, stage(self.source, self.out))

    def test_unreviewed_local_import_rejected(self):
        (self.source / 'vertical/unreviewed.py').write_text('pass\n')
        (self.source / 'vertical/core_read.py').write_text('def f():\n    import unreviewed\n')
        with self.assertRaisesRegex(ValueError, 'unreviewed local dependency: unreviewed'):
            stage(self.source, self.out)
        self.assertFalse(self.out.exists())

    def test_missing_transport_rejected(self):
        (self.source / 'vertical/bounded_http_transport.py').unlink()
        with self.assertRaisesRegex(ValueError, 'missing or linked source'):
            stage(self.source, self.out)
        self.assertFalse(self.out.exists())

    def test_linked_source_rejected(self):
        path = self.source / 'vertical/bounded_http_transport.py'
        path.unlink()
        path.symlink_to(self.source / 'vertical/core_read.py')
        with self.assertRaisesRegex(ValueError, 'missing or linked source'):
            stage(self.source, self.out)
        self.assertFalse(self.out.exists())

    def test_unpinned_worker_and_existing_output_rejected(self):
        with self.assertRaises(ValueError):
            stage(self.source, self.out, WORKER.split('@')[0] + ':latest')
        self.assertFalse(self.out.exists())
        self.out.mkdir()
        marker = self.out / 'keep'
        marker.write_text('keep')
        with self.assertRaises(ValueError):
            stage(self.source, self.out)
        self.assertEqual(marker.read_text(), 'keep')

    def test_actual_checkout_inventory(self):
        source = HERE.parents[1]
        self.assertTrue((source / 'vertical/core_read.py').is_file(), 'actual V3 checkout required')
        self.assert_inventory(source, stage(source, self.out))


if __name__ == '__main__':
    unittest.main()
