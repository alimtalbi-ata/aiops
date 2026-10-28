import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from demo import evidence_video_bundle as bundle


def png(width=320, height=200):
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload +
                struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
    ihdr = struct.pack(">II", width, height) + bytes((8, 2, 0, 0, 0))
    scanlines = (bytes((0,)) + bytes(width * 3)) * height
    return (bytes.fromhex("89504e470d0a1a0a") + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


class EvidenceVideoBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.evidence = root / "evidence"
        self.output = root / "output"
        self.evidence.mkdir()
        self.output.mkdir(mode=0o700)
        self.entries = []
        for service in bundle.SERVICES:
            data = png()
            (self.evidence / (service + ".png")).write_bytes(data)
            self.entries.append({"service": service, "file": service + ".png",
                                 "sha256": hashlib.sha256(data).hexdigest(),
                                 "captured_at_utc": "2026-10-27T19:00:00Z",
                                 "source_url": "https://example.invalid/" + service,
                                 "run_id": "RUN-001", "incident_id": "INC-001",
                                 "ticket_id": "TCK-001", "session_label": "operator-unreviewed"})
        self.manifest = root / "manifest.json"
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps({"schema_version": 1,
            "provenance": "OPERATOR_SUPPLIED_UNATTESTED", "captures": self.entries}))

    def test_subtitle_timing_and_no_sensitive_ids(self):
        text = bundle.subtitles([{"service": s} for s in bundle.SERVICES], 2)
        self.assertIn("00:00:00,000 --> 00:00:02,000", text)
        self.assertIn("00:00:08,000 --> 00:00:10,000", text)
        self.assertNotIn("RUN-001", text)
        self.assertEqual(text.count("capture opérateur non attestée"), 5)

    def test_inconsistent_incident_rejected_before_render(self):
        self.entries[2]["incident_id"] = "INC-OTHER"
        self.write_manifest()
        with patch.object(bundle, "render") as render:
            with self.assertRaisesRegex(ValueError, "inconsistent correlation"):
                bundle.build_bundle(self.evidence, self.manifest, self.output)
            render.assert_not_called()

    def test_url_query_secret_rejected(self):
        self.entries[0]["source_url"] += "?token=secret"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "expose secrets"):
            bundle.build_bundle(self.evidence, self.manifest, self.output)

    def test_duplicate_json_key_rejected(self):
        self.manifest.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            bundle.build_bundle(self.evidence, self.manifest, self.output)


    def test_manifest_symlink_and_fifo_rejected_before_render(self):
        """Untrusted manifest path must never be followed or opened as a FIFO."""
        import os
        original = self.manifest.read_bytes()
        real = self.manifest.parent / "real-manifest.json"
        real.write_bytes(original)
        self.manifest.unlink()
        self.manifest.symlink_to(real)
        with patch.object(bundle, "render") as render:
            with self.assertRaises(ValueError):
                bundle.build_bundle(self.evidence, self.manifest, self.output)
            render.assert_not_called()
        self.manifest.unlink()
        os.mkfifo(self.manifest)
        with patch.object(bundle, "render") as render:
            with self.assertRaises(ValueError):
                bundle.build_bundle(self.evidence, self.manifest, self.output)
            render.assert_not_called()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_manifest_read_rejects_mutation_during_open_descriptor(self):
        """A manifest rewritten after its initial fstat must fail closed."""
        from demo import evidence_snapshot as snapshot
        original = self.manifest.read_bytes()
        real_fstat = snapshot.os.fstat
        touched = False

        def mutate_on_first_stat(fd):
            nonlocal touched
            result = real_fstat(fd)
            if not touched:
                touched = True
                self.manifest.write_bytes(original + b" ")
            return result

        with patch.object(snapshot.os, "fstat", side_effect=mutate_on_first_stat):
            with patch.object(bundle, "render") as render:
                with self.assertRaisesRegex(ValueError, "file changed during read"):
                    bundle.build_bundle(self.evidence, self.manifest, self.output)
                render.assert_not_called()
        self.assertTrue(touched)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_manifest_over_size_limit_rejected(self):
        self.manifest.write_bytes(b" " * (256 * 1024 + 1))
        with patch.object(bundle, "render") as render:
            with self.assertRaisesRegex(ValueError, "bounded regular file"):
                bundle.build_bundle(self.evidence, self.manifest, self.output)
            render.assert_not_called()

    def test_world_readable_output_rejected(self):
        self.output.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "private existing"):
            bundle.build_bundle(self.evidence, self.manifest, self.output)

    def test_existing_output_rejected(self):
        (self.output / bundle.NAMES[1]).write_text("already exists")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            bundle.build_bundle(self.evidence, self.manifest, self.output)

    def test_missing_correlation_rejected(self):
        self.entries[0].pop("ticket_id")
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "missing or unsafe correlation"):
            bundle.build_bundle(self.evidence, self.manifest, self.output)

    def test_bad_seconds_rejected(self):
        with self.assertRaises(ValueError):
            bundle.build_bundle(self.evidence, self.manifest, self.output, 0)

    def test_tampered_capture_rejected_before_render(self):
        (self.evidence / "portal.png").write_bytes(b"tampered")
        with patch.object(bundle, "render") as render:
            with self.assertRaises(ValueError):
                bundle.build_bundle(self.evidence, self.manifest, self.output)
            render.assert_not_called()

    def test_output_symlink_rejected(self):
        link = self.output.parent / "link"
        link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "private existing"):
            bundle.build_bundle(self.evidence, self.manifest, link)

    def test_source_swap_between_verification_and_pin_fails_closed(self):
        real_pin = bundle.pin_captures

        def mutate_then_pin(root, stage, captures):
            # Still a valid PNG: only the manifest hash can reject the swap.
            (root / "portal.png").write_bytes(png(width=321))
            return real_pin(root, stage, captures)

        with patch.object(bundle, "pin_captures", side_effect=mutate_then_pin):
            with patch.object(bundle, "render") as render:
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    bundle.build_bundle(self.evidence, self.manifest, self.output)
                render.assert_not_called()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_render_uses_pinned_bytes_after_source_changes(self):
        original = (self.evidence / "portal.png").read_bytes()
        seen = []

        def inspect_render(pinned, captures, output, seconds):
            seen.append(pinned)
            self.assertNotEqual(pinned.resolve(), self.evidence.resolve())
            self.assertEqual((pinned / "portal.png").read_bytes(), original)
            (self.evidence / "portal.png").write_bytes(b"source changed after pin")
            self.assertEqual((pinned / "portal.png").read_bytes(), original)
            raise RuntimeError("render intercepted after snapshot")

        with patch.object(bundle, "render", side_effect=inspect_render):
            with self.assertRaisesRegex(RuntimeError, "render intercepted"):
                bundle.build_bundle(self.evidence, self.manifest, self.output)
        self.assertEqual(len(seen), 1)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_no_partial_output_on_render_failure(self):
        with patch.object(bundle, "render", side_effect=RuntimeError("encoder failed")):
            with self.assertRaisesRegex(RuntimeError, "encoder failed"):
                bundle.build_bundle(self.evidence, self.manifest, self.output, 2)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_source_manifest_metadata_allowlist_fail_closed(self):
        # No unreviewed credential/claim fields may enter a packaged manifest.
        for field, value in (("access_token", "secret"), ("reviewed", True)):
            with self.subTest(field=field):
                self.entries[0][field] = value
                self.write_manifest()
                with patch.object(bundle, "render") as render:
                    with self.assertRaisesRegex(ValueError, "source capture metadata"):
                        bundle.build_bundle(self.evidence, self.manifest, self.output)
                    render.assert_not_called()
                del self.entries[0][field]
        self.write_manifest()
        for field, value in (("session_cookie", "secret"), ("runtime_authenticated", True)):
            with self.subTest(field=field):
                data = json.loads(self.manifest.read_text())
                data[field] = value
                self.manifest.write_text(json.dumps(data))
                with patch.object(bundle, "render") as render:
                    with self.assertRaisesRegex(ValueError, "source capture manifest"):
                        bundle.build_bundle(self.evidence, self.manifest, self.output)
                    render.assert_not_called()
        self.write_manifest()

    def test_browser_unreviewed_metadata_remains_supported(self):
        manifest = json.loads(self.manifest.read_text())
        for entry in manifest["captures"]:
            entry.update({"capture_method": "PLAYWRIGHT_OPERATOR_SESSION_UNREVIEWED",
                          "runtime_authenticated": False, "production_qualified": False})
        manifest["runtime_authenticated"] = False
        manifest["production_qualified"] = False
        bundle.validate_source_manifest(manifest)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "real ffmpeg/ffprobe unavailable")
    def test_real_mp4_srt_receipt_offline(self):
        result = bundle.build_bundle(self.evidence, self.manifest, self.output, 2)
        self.assertFalse(result["runtime_authenticated"])
        self.assertFalse(result["production_qualified"])
        self.assertEqual(result["capture_count"], 5)
        self.assertEqual(result["source_manifest_sha256"], hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        self.assertTrue(9.75 <= result["video"]["duration_seconds"] <= 10.25)
        self.assertEqual(bundle._sha(self.output / bundle.NAMES[0]), result["video"]["sha256"])
        self.assertEqual(bundle._sha(self.output / bundle.NAMES[1]), result["subtitles"]["sha256"])
        self.assertEqual(json.loads((self.output / bundle.NAMES[2]).read_text()), result)
        self.assertEqual(len(list(self.output.iterdir())), 3)
        self.assertTrue(all((p.stat().st_mode & 0o077) == 0 for p in self.output.iterdir()))


if __name__ == "__main__":
    unittest.main()
