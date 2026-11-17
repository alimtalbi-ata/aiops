"""Offline tests for the ACME qualification addon; no browser or network."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import struct
import zlib
import unittest

from scripts.acme_qualification_addon import (
    SCENES, inspect_host_receipt, inspect_scenes, png_structure_valid, qualify,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/acme/valid.json"
NOW = dt.datetime(2026, 11, 16, 17, 0, tzinfo=dt.timezone.utc)
SHA = "a" * 40


class QualificationAddonTests(unittest.TestCase):
    def receipt(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_offline_valid_never_runtime_attested(self):
        result = qualify(self.receipt(), expected_sha=SHA, now=NOW)
        self.assertEqual(result["verdict"], "OFFLINE_SIMULATION_GATE_PASS_ONLY")
        self.assertEqual(result["runtime_e2e"], "NOT_VERIFIED")
        self.assertEqual(result["live"], "NO_GO")
        self.assertEqual(result["host_receipt_metadata"]["status"], "NOT_QUALIFIED")

    def test_negative_receipt_no_go(self):
        receipt = self.receipt()
        receipt["mode"] = "LIVE"
        self.assertEqual(qualify(receipt, now=NOW)["verdict"], "NO_GO")

    def test_host_receipt_provenance_mismatch(self):
        host = {"schema": "aiops.portal-host-playwright-snapshots.v1",
                "status": "PASS_ANONYMOUS_SYNTHETIC_BROWSER_ONLY",
                "stable_checkout_sha": "b" * 40, "portal_image_id": "sha256:" + "c" * 64,
                "live_effects": 0, "screenshots": [{"name": "01-overview.png"}],
                "page_errors_count": 0, "unexpected_console_errors_count": 0,
                "failed_requests_count": 0, "blocked_requests_count": 0}
        self.assertIn("HOST_SHA_MISMATCH", inspect_host_receipt(host, SHA))
        host["stable_checkout_sha"] = SHA
        self.assertEqual(inspect_host_receipt(host, SHA), [])

    def test_seven_scenes_integrity_and_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # Complete synthetic PNG structure, not browser evidence.
            def chunk(kind, payload):
                return (struct.pack(">I", len(payload)) + kind + payload +
                        struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))
            ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            pixels = zlib.compress(bytes([0, 0, 0, 0]))
            raw = (bytes([137, 80, 78, 71, 13, 10, 26, 10]) +
                   chunk(b"IHDR", ihdr) + chunk(b"IDAT", pixels) +
                   chunk(b"IEND", b""))
            self.assertTrue(png_structure_valid(raw))
            self.assertFalse(png_structure_valid(raw[:-5]))
            corrupt_crc = bytearray(raw)
            corrupt_crc[29] ^= 1
            self.assertFalse(png_structure_valid(bytes(corrupt_crc)))
            records = []
            for sid in SCENES:
                name = sid + ".png"
                (root / name).write_bytes(raw)
                records.append({"id": sid, "file": name, "status": "PASS",
                                "sha256": hashlib.sha256(raw).hexdigest(),
                                "simulation_visible": True, "external_requests": 0})
            manifest = {"schema": "aiops.acme-scene-evidence.v1",
                        "source_sha": SHA, "scenario_id": "ACME-SAN-PAYMENTS",
                        "tenant_id": "ACME-TEST", "mode": "SIMULATION",
                        "live": "NO_GO", "scenes": records}
            self.assertEqual(inspect_scenes(manifest, root, SHA), [])
            result = qualify(self.receipt(), None, manifest, root, SHA, NOW)
            self.assertEqual(result["runtime_e2e"], "NOT_VERIFIED")
            records[0]["simulation_visible"] = False
            self.assertIn("SCENE_SIMULATION_NOT_VERIFIED", inspect_scenes(manifest, root, SHA))
            records[0]["simulation_visible"] = True
            (root / "noc.png").write_bytes(b"corrupt")
            self.assertIn("SCENE_HASH_MISMATCH", inspect_scenes(manifest, root, SHA))

    def test_invalid_and_missing_scenes(self):
        self.assertIn("SCENES_COUNT_INVALID", inspect_scenes(
            {"schema": "aiops.acme-scene-evidence.v1", "source_sha": SHA,
             "scenario_id": "ACME-SAN-PAYMENTS", "tenant_id": "ACME-TEST",
             "mode": "SIMULATION", "live": "NO_GO", "scenes": []},
            Path("."), SHA))
        self.assertEqual(qualify(self.receipt(), expected_sha="not-sha", now=NOW)["live"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
