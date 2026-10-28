"""Offline negative/positive tests; fixtures are NOT application captures or MP4 proof."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from demo import evidence_bundle_audit as audit
from demo.evidence_video import SERVICES, verify


def _png():
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))
    width, height = 320, 200
    header = struct.pack(">II", width, height) + bytes((8, 2, 0, 0, 0))
    rows = (b"\x00" + bytes(width * 3)) * height
    return bytes.fromhex("89504e470d0a1a0a") + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


class BundleAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.bundle = root / "bundle"
        self.captures = root / "captures"
        self.bundle.mkdir(mode=0o700)
        self.captures.mkdir()
        entries = []
        for service in SERVICES:
            data = _png()
            name = service + ".png"
            (self.captures / name).write_bytes(data)
            entries.append({"service": service, "file": name,
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "captured_at_utc": "2026-10-28T03:00:00Z",
                            "source_url": "https://example.invalid/" + service})
        captures = verify(self.captures, {"schema_version": 1,
                          "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
                          "captures": entries})
        self.mp4 = self.bundle / audit.NAMES[0]
        self.srt = self.bundle / audit.NAMES[1]
        self.mp4.write_bytes(b"offline hash-only fixture; NOT playable video")
        self.srt.write_bytes(audit.canonical_subtitles(captures, 2).encode("utf-8"))
        self.receipt = {
            "schema_version": 1, "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
            "runtime_authenticated": False, "production_qualified": False,
            "capture_count": 5,
            "correlation": {"run_id": "RUN-001", "incident_id": "INC-001",
                            "ticket_id": "TCK-001", "session_label": "offline-test"},
            "captures": captures,
            "video": {"file": audit.NAMES[0],
                      "sha256": hashlib.sha256(self.mp4.read_bytes()).hexdigest(),
                      "duration_seconds": 10.0, "codec": "h264", "resolution": "1920x1080"},
            "subtitles": {"file": audit.NAMES[1],
                          "sha256": hashlib.sha256(self.srt.read_bytes()).hexdigest()},
        }
        self.manifest = root / "capture-manifest.json"
        self.source = {
            "schema_version": 1, "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
            "captures": [{**entry, **self.receipt["correlation"]} for entry in entries],
        }
        self.write_source()
        self.rebind_manifest_hash()
        self.write_receipt()

    def write_source(self):
        self.manifest.write_text(json.dumps(self.source), encoding="utf-8")

    def rebind_manifest_hash(self):
        self.receipt["source_manifest_sha256"] = hashlib.sha256(
            self.manifest.read_bytes()).hexdigest()

    def write_receipt(self):
        (self.bundle / audit.NAMES[2]).write_text(json.dumps(self.receipt), encoding="utf-8")

    def run_audit(self):
        return audit.audit_bundle(self.bundle, self.captures, self.manifest)

    def test_local_bytes_verified_but_never_runtime_attested(self):
        result = self.run_audit()
        self.assertEqual(result["status"], "LOCAL_BYTES_VERIFIED_UNATTESTED")
        self.assertEqual(result["capture_count"], 5)
        self.assertFalse(result["media_decoded_by_auditor"])
        self.assertFalse(result["runtime_authenticated"])
        self.assertFalse(result["production_qualified"])
        self.assertFalse(result["live_action_authorized"])

    def test_tampered_mp4_srt_and_png_rejected(self):
        for target in (self.mp4, self.srt, self.captures / "portal.png"):
            with self.subTest(target=target.name):
                original = target.read_bytes()
                target.write_bytes(original + b"tamper")
                with self.assertRaises(ValueError):
                    self.run_audit()
                target.write_bytes(original)

    def test_rehashed_sensitive_or_reordered_subtitles_rejected(self):
        """Rehashing an injected SRT must not launder it as verified evidence."""
        original = self.srt.read_text(encoding="utf-8")
        for changed in (original.replace("Portail AIOps", "INC-001 SECRET"),
                        original.replace("Thruk", "Grafana", 1)):
            with self.subTest(caption=changed[:60]):
                self.srt.write_text(changed, encoding="utf-8")
                self.receipt["subtitles"]["sha256"] = hashlib.sha256(
                    self.srt.read_bytes()).hexdigest()
                self.write_receipt()
                with self.assertRaisesRegex(ValueError, "noncanonical subtitles"):
                    self.run_audit()
        self.srt.write_text(original, encoding="utf-8")
        self.receipt["subtitles"]["sha256"] = hashlib.sha256(
            self.srt.read_bytes()).hexdigest()
        self.write_receipt()
        self.assertEqual(self.run_audit()["status"], "LOCAL_BYTES_VERIFIED_UNATTESTED")

    def test_nonfinite_or_noncanonical_scene_duration_rejected(self):
        for duration in (True, float("nan"), float("inf"), 10 ** 400, 10.4, 11.0, 12.0, 100.5):
            with self.subTest(duration=duration):
                self.receipt["video"]["duration_seconds"] = duration
                self.write_receipt()
                with self.assertRaisesRegex(ValueError, "video receipt|duration"):
                    self.run_audit()
        self.receipt["video"]["duration_seconds"] = 10.0
        self.write_receipt()
        self.assertEqual(self.run_audit()["capture_count"], 5)

    def test_duplicate_json_keys_rejected(self):
        (self.bundle / audit.NAMES[2]).write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            self.run_audit()

    def test_provenance_escalation_and_unknown_flags_rejected(self):
        for key, value in (("runtime_authenticated", True),
                           ("production_qualified", True),
                           ("provenance", "LIVE"),
                           ("capture_count", True),
                           ("live_action_authorized", True)):
            with self.subTest(key=key):
                self.receipt[key] = value
                self.write_receipt()
                with self.assertRaises(ValueError):
                    self.run_audit()
                if key == "live_action_authorized":
                    del self.receipt[key]
                elif key == "provenance":
                    self.receipt[key] = "OPERATOR_SUPPLIED_UNATTESTED"
                elif key == "capture_count":
                    self.receipt[key] = 5
                else:
                    self.receipt[key] = False

    def test_traversal_and_wrong_media_filename_rejected(self):
        for name in ("../outside.mp4", "/tmp/forged.mp4", "video.mp4"):
            with self.subTest(name=name):
                self.receipt["video"]["file"] = name
                self.write_receipt()
                with self.assertRaisesRegex(ValueError, "video receipt"):
                    self.run_audit()
        self.receipt["video"]["file"] = audit.NAMES[0]

    def test_symlinked_receipt_and_media_rejected(self):
        for target in (self.mp4, self.bundle / audit.NAMES[2]):
            with self.subTest(name=target.name):
                original = target.read_bytes()
                target.unlink()
                real = self.bundle.parent / ("outside-" + target.name)
                real.write_bytes(original)
                target.symlink_to(real)
                with self.assertRaises(OSError):
                    self.run_audit()
                target.unlink()
                target.write_bytes(original)

    def test_world_readable_bundle_directory_rejected(self):
        self.bundle.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "private"):
            self.run_audit()

    def test_noncanonical_capture_order_rejected(self):
        self.receipt["captures"].reverse()
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "noncanonical"):
            self.run_audit()

    def test_missing_or_invalid_correlation_rejected(self):
        self.receipt["correlation"]["run_id"] = "unsafe value"
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "correlation"):
            self.run_audit()

    def test_real_offline_ffmpeg_bundle_roundtrip(self):
        """Technical FFmpeg integration only; no application screenshots."""
        import shutil
        from demo.evidence_video_bundle import build_bundle

        self.assertIsNotNone(shutil.which("ffmpeg"), "FFmpeg required by CI")
        self.assertIsNotNone(shutil.which("ffprobe"), "FFprobe required by CI")
        root = self.bundle.parent
        manifest = root / "input-manifest.json"
        # The receipt adds a derived status that is NOT a source-manifest field.
        entries = [{key: value for key, value in
                    {**entry, **self.receipt["correlation"]}.items()
                    if key != "status"}
                   for entry in self.receipt["captures"]]
        manifest.write_text(json.dumps({"schema_version": 1,
                            "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
                            "captures": entries}), encoding="utf-8")
        rendered = root / "rendered"
        rendered.mkdir(mode=0o700)
        built = build_bundle(self.captures, manifest, rendered, seconds=2)
        self.assertEqual(built["provenance"], "OPERATOR_SUPPLIED_UNATTESTED")
        result = audit.audit_bundle(rendered, self.captures, manifest)
        self.assertEqual(result["status"], "LOCAL_BYTES_VERIFIED_UNATTESTED")
        self.assertFalse(result["runtime_authenticated"])
        self.assertFalse(result["media_decoded_by_auditor"])

    def test_rehashed_receipt_cannot_relabel_or_leak_source(self):
        # No image bytes change; the adversary rewrites only receipt metadata.
        original = self.receipt["captures"][0].copy()
        for key, value in (
            ("file", "thruk.png"),
            ("source_url", "https://example.invalid/portal?api_key=secret"),
            ("source_url", "https://example.invalid/portal#token"),
        ):
            with self.subTest(field=key, value=value):
                self.receipt["captures"][0] = {**original, key: value}
                self.write_receipt()
                with self.assertRaisesRegex(ValueError, "filename mismatch|expose secrets"):
                    self.run_audit()
        self.receipt["captures"][0] = original
        self.write_receipt()
        self.assertEqual(self.run_audit()["status"], "LOCAL_BYTES_VERIFIED_UNATTESTED")

    def test_source_manifest_changed_without_rehash_rejected(self):
        self.source["captures"][0]["incident_id"] = "INC-ALTERED"
        self.write_source()
        with self.assertRaisesRegex(ValueError, "source capture manifest checksum"):
            self.run_audit()

    def test_rehashed_source_manifest_cannot_change_correlation_or_capture(self):
        original = json.loads(json.dumps(self.source))
        for field, value in (("run_id", "RUN-OTHER"),
                             ("source_url", "https://example.invalid/other")):
            with self.subTest(field=field):
                self.source = json.loads(json.dumps(original))
                self.source["captures"][0][field] = value
                self.write_source()
                self.rebind_manifest_hash()
                self.write_receipt()
                with self.assertRaisesRegex(ValueError, "inconsistent correlation field|source manifest correlation|source manifest captures"):
                    self.run_audit()
        self.source = original
        self.write_source()
        self.rebind_manifest_hash()
        self.write_receipt()
        self.assertEqual(self.run_audit()["status"], "LOCAL_BYTES_VERIFIED_UNATTESTED")

    def test_rehashed_source_and_receipt_cannot_hide_cross_session_capture(self):
        # Both JSON objects and their declared SHA-256 are updated together.
        # A hash-only auditor would accept this stale fifth screenshot.
        stamp = "2026-10-28T03:15:01Z"
        self.source["captures"][-1]["captured_at_utc"] = stamp
        self.receipt["captures"][-1]["captured_at_utc"] = stamp
        self.write_source()
        self.rebind_manifest_hash()
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "15-minute"):
            self.run_audit()

    def test_rehashed_source_manifest_live_escalation_rejected(self):
        for key, value in (("provenance", "LIVE"),
                           ("runtime_authenticated", True),
                           ("production_qualified", True)):
            with self.subTest(key=key):
                original = self.source.get(key)
                self.source[key] = value
                self.write_source()
                self.rebind_manifest_hash()
                self.write_receipt()
                with self.assertRaisesRegex(ValueError, "source capture manifest provenance"):
                    self.run_audit()
                if original is None:
                    del self.source[key]
                else:
                    self.source[key] = original

    def test_rehashed_unknown_source_metadata_rejected(self):
        # Recalculating the manifest hash must not launder credentials or claims.
        for scope, field, value in (("root", "session_cookie", "secret"),
                                    ("capture", "access_token", "secret"),
                                    ("capture", "privacy_reviewed", True),
                                    ("capture", "status", "BYTES_HASH_VERIFIED_NOT_RUNTIME_ATTESTED"),
                                    ("capture", "capture_method", "UNVERIFIED"),
                                    ("capture", "runtime_authenticated", True)):
            with self.subTest(scope=scope, field=field):
                target = self.source if scope == "root" else self.source["captures"][0]
                target[field] = value
                self.write_source()
                self.rebind_manifest_hash()
                self.write_receipt()
                with self.assertRaisesRegex(ValueError, "source capture"):
                    self.run_audit()
                del target[field]
        self.write_source()
        self.rebind_manifest_hash()
        self.write_receipt()
        self.assertEqual(self.run_audit()["status"], "LOCAL_BYTES_VERIFIED_UNATTESTED")

    def test_source_manifest_missing_or_symlink_rejected(self):
        original = self.manifest.read_bytes()
        self.manifest.unlink()
        with self.assertRaises(OSError):
            self.run_audit()
        outside = self.manifest.parent / "source-real.json"
        outside.write_bytes(original)
        self.manifest.symlink_to(outside)
        with self.assertRaises(OSError):
            self.run_audit()

    def test_missing_media_rejected(self):
        self.mp4.unlink()
        with self.assertRaises(OSError):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
