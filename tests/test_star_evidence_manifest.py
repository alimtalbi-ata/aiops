"""Offline tests for STAR screenshot evidence byte verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from demo.star_evidence_manifest import audit_manifest
from demo.star_snapshot_choreography import CUES


def png_bytes(width: int = 2, height: int = 2, idat_override: bytes | None = None) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanline = b"\x00" + b"\x10\x20\x30" * width
    raw = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    compressed = zlib.compress(scanline * height) if idat_override is None else idat_override
    raw += chunk(b"IDAT", compressed)
    raw += chunk(b"IEND", b"")
    return raw


class StarEvidenceManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.entries = []
        for index, cue in enumerate(CUES):
            rel = f"evidence/{cue.cue}.png"
            raw = png_bytes()
            (self.root / rel).write_bytes(raw)
            self.entries.append({
                "cue": cue.cue,
                "service": cue.service,
                "view": cue.view,
                "required_state": cue.required_state,
                "source_url": f"https://demo.example/{cue.service}/{cue.view}",
                "captured_at_utc": "2026-10-27T10:00:00Z",
                "run_id": "SIM-STAR-0001",
                "incident_id": "INC-SIM-0001",
                "ticket_id": None,
                "screenshot_path": rel,
                "screenshot_sha256": hashlib.sha256(raw).hexdigest(),
            })
        self.manifest = self.root / "manifest.json"
        self.write_manifest()
        self.allowed = {"https://demo.example"}

    def tearDown(self):
        self.tmp.cleanup()

    def write_manifest(self, **overrides):
        payload = {
            "schema_version": 1,
            "provenance": "OPERATOR_SUPPLIED_SCREENSHOTS_UNATTESTED",
            "captures": self.entries,
        }
        payload.update(overrides)
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")

    def audit(self):
        return audit_manifest(self.manifest, self.root, self.allowed)

    def test_all_nine_pngs_are_hash_verified_but_never_attested(self):
        result = self.audit()
        self.assertTrue(result["complete_byte_set"])
        self.assertEqual(result["capture_count"], 9)
        self.assertEqual({row["status"] for row in result["captures"]}, {"BYTES_VERIFIED_UNATTESTED"})
        self.assertFalse(result["application_identity_authenticated"])
        self.assertFalse(result["runtime_event_authenticated"])
        self.assertFalse(result["business_state_validated"])
        self.assertFalse(result["human_approval_authenticated"])
        self.assertFalse(result["live_action_authorized"])
        self.assertFalse(result["production_qualified"])

    def test_missing_checkpoint_fails_closed(self):
        self.entries.pop()
        self.write_manifest()
        result = self.audit()
        self.assertFalse(result["complete_byte_set"])
        self.assertEqual(result["captures"][-1]["status"], "MISSING")

    def test_hash_mismatch_is_rejected(self):
        self.entries[0]["screenshot_sha256"] = "0" * 64
        self.write_manifest()
        result = self.audit()
        self.assertEqual(result["captures"][0]["status"], "REJECTED")
        self.assertFalse(result["complete_byte_set"])

    def test_duplicate_json_object_keys_are_rejected(self):
        self.manifest.write_text(
            '{"schema_version":1,"schema_version":1,"provenance":"OPERATOR_SUPPLIED_SCREENSHOTS_UNATTESTED","captures":[]}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
            self.audit()

    def test_non_utc_offset_is_rejected_for_utc_field(self):
        self.entries[0]["captured_at_utc"] = "2026-10-27T11:00:00+01:00"
        self.write_manifest()
        self.assertEqual(self.audit()["captures"][0]["status"], "REJECTED")

    def test_symlink_manifest_is_rejected(self):
        alias = self.root / "manifest-link.json"
        alias.symlink_to(self.manifest)
        with self.assertRaises(ValueError):
            audit_manifest(alias, self.root, self.allowed)

    def test_symlink_evidence_root_is_rejected(self):
        alias = self.root / "evidence-link"
        alias.symlink_to(self.evidence, target_is_directory=True)
        with self.assertRaises(ValueError):
            audit_manifest(self.manifest, alias, self.allowed)

    def test_unapproved_origin_is_rejected(self):
        self.entries[0]["source_url"] = "https://evil.example/login"
        self.write_manifest()
        self.assertEqual(self.audit()["captures"][0]["status"], "REJECTED")

    def test_path_traversal_is_rejected(self):
        self.entries[0]["screenshot_path"] = "../outside.png"
        self.write_manifest()
        self.assertEqual(self.audit()["captures"][0]["status"], "REJECTED")

    def test_symlink_screenshot_is_rejected(self):
        path = self.root / self.entries[0]["screenshot_path"]
        target = self.root / "target.png"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
        self.write_manifest()
        self.assertEqual(self.audit()["captures"][0]["status"], "REJECTED")

    def test_corrupt_png_crc_is_rejected(self):
        path = self.root / self.entries[0]["screenshot_path"]
        raw = bytearray(path.read_bytes())
        raw[-5] ^= 0xFF
        path.write_bytes(raw)
        self.entries[0]["screenshot_sha256"] = hashlib.sha256(raw).hexdigest()
        self.write_manifest()
        self.assertEqual(self.audit()["captures"][0]["status"], "REJECTED")

    def test_duplicate_cue_is_not_accepted(self):
        self.entries.append(dict(self.entries[0]))
        self.write_manifest()
        result = self.audit()
        self.assertFalse(result["complete_byte_set"])
        self.assertEqual(result["captures"][0]["status"], "REJECTED_DUPLICATE_CUE")

    def test_invalid_zlib_stream_is_rejected_even_with_valid_chunk_crc_and_hash(self):
        path = self.root / self.entries[0]["screenshot_path"]
        raw = png_bytes(idat_override=b"not-a-zlib-stream")
        path.write_bytes(raw)
        self.entries[0]["screenshot_sha256"] = hashlib.sha256(raw).hexdigest()
        self.write_manifest()
        self.assertEqual(self.audit()["captures"][0]["status"], "REJECTED")

    def test_invalid_scanline_filter_is_rejected_even_with_matching_hash(self):
        path = self.root / self.entries[0]["screenshot_path"]
        bad_scanlines = (b"\x05" + b"\x10\x20\x30" * 2) * 2
        raw = png_bytes(idat_override=zlib.compress(bad_scanlines))
        path.write_bytes(raw)
        self.entries[0]["screenshot_sha256"] = hashlib.sha256(raw).hexdigest()
        self.write_manifest()
        self.assertEqual(self.audit()["captures"][0]["status"], "REJECTED")

    def test_png_without_idat_is_rejected_even_with_matching_hash(self):
        path = self.root / self.entries[0]["screenshot_path"]
        raw = path.read_bytes()
        rebuilt = bytearray(raw[:8])
        offset = 8
        while offset < len(raw):
            length = struct.unpack(">I", raw[offset:offset + 4])[0]
            end = offset + 12 + length
            chunk_type = raw[offset + 4:offset + 8]
            if chunk_type != b"IDAT":
                rebuilt.extend(raw[offset:end])
            offset = end
        path.write_bytes(rebuilt)
        self.entries[0]["screenshot_sha256"] = hashlib.sha256(rebuilt).hexdigest()
        self.write_manifest()
        self.assertEqual(self.audit()["captures"][0]["status"], "REJECTED")

    def test_metadata_cannot_promote_runtime_attestation(self):
        self.entries[0]["runtime_authenticated"] = True
        self.entries[0]["human_approval_authenticated"] = True
        self.write_manifest()
        result = self.audit()
        self.assertFalse(result["captures"][0]["runtime_authenticated"])
        self.assertFalse(result["captures"][0]["human_approval_authenticated"])


if __name__ == "__main__":
    unittest.main()
