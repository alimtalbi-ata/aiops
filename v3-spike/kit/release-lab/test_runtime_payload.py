"""Synthetic disk contract and optional integration with the actual staged support."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from runtime_payload import FILES, MANIFEST, stage, verify

SOURCE_SHA = 'a' * 40


class RuntimePayloadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        for name in FILES:
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('fixture:' + name)
        (self.source / 'private-unrelated.txt').write_text('must not transfer')
        self.dest = self.root / 'payload'

    def staged(self):
        return stage(self.source, self.dest, SOURCE_SHA)

    def test_roundtrip(self):
        r = self.staged()
        self.assertEqual(verify(self.dest, r['manifest_sha256'], SOURCE_SHA), r)
        self.assertEqual(r['files'], len(FILES))
        self.assertFalse((self.dest/'private-unrelated.txt').exists())
        self.assertFalse((self.dest/'.git').exists())
        other = stage(self.source, self.root/'second', SOURCE_SHA)
        self.assertEqual(r, other)

    def test_bad_expected_manifest(self):
        self.staged()
        with self.assertRaises(ValueError):
            verify(self.dest, 'sha256:'+'0'*64, SOURCE_SHA)

    def test_wrong_source(self):
        r = self.staged()
        with self.assertRaises(ValueError):
            verify(self.dest, r['manifest_sha256'], 'b'*40)

    def test_tampered_file(self):
        r = self.staged()
        (self.dest / sorted(FILES)[0]).write_text('altered')
        with self.assertRaises(ValueError):
            verify(self.dest, r['manifest_sha256'], SOURCE_SHA)

    def test_extra_file(self):
        r = self.staged()
        (self.dest/'unexpected').write_text('extra')
        with self.assertRaises(ValueError):
            verify(self.dest, r['manifest_sha256'], SOURCE_SHA)

    def test_extra_directory(self):
        r = self.staged()
        (self.dest/'unexpected').mkdir()
        with self.assertRaises(ValueError):
            verify(self.dest, r['manifest_sha256'], SOURCE_SHA)

    def test_missing_file(self):
        r = self.staged()
        (self.dest/sorted(FILES)[0]).unlink()
        with self.assertRaises(ValueError):
            verify(self.dest, r['manifest_sha256'], SOURCE_SHA)

    def test_linked_source(self):
        p = self.source/sorted(FILES)[0]
        p.unlink()
        p.symlink_to(self.source/'private-unrelated.txt')
        with self.assertRaises((ValueError, OSError)):
            self.staged()
        self.assertFalse(self.dest.exists())

    def test_linked_destination_file(self):
        r = self.staged()
        p = self.dest/sorted(FILES)[0]
        raw = p.read_bytes()
        outside = self.root/'outside'
        outside.write_bytes(raw)
        p.unlink()
        p.symlink_to(outside)
        with self.assertRaises(ValueError):
            verify(self.dest, r['manifest_sha256'], SOURCE_SHA)

    def test_destination_exists(self):
        self.dest.mkdir()
        marker = self.dest/'keep'
        marker.write_text('keep')
        with self.assertRaises(FileExistsError):
            self.staged()
        self.assertEqual(marker.read_text(), 'keep')

    def test_destination_inside_source(self):
        with self.assertRaises(ValueError):
            stage(self.source, self.source/'nested', SOURCE_SHA)
        self.assertFalse((self.source/'nested').exists())

    def test_source_file_absent(self):
        (self.source/sorted(FILES)[0]).unlink()
        with self.assertRaises(OSError):
            self.staged()
        self.assertFalse(self.dest.exists())

if __name__ == '__main__':
    unittest.main()
