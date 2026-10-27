"""Offline synthetic contract for Chromium manifest -> STAR storyboard."""
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from demo.star_browser_manifest_gate import verify_browser_manifests
from demo.star_capture_set_replay_gate import verify_pinned_replay_captures
from demo.star_portal_storyboard import storyboard


def chunk(kind, data=b""):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


PNG = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND"))
EXPECTED = {"run_id": "RUN-ACME-001", "correlation_id": "CORR-ACME-001", "events": {"detect": "DASH-7"}}




def _build_v2_capture_set(root):
    """Build a complete nine-cue synthetic v2 set in a temporary directory."""
    from datetime import datetime, timedelta, timezone
    from demo.star_snapshot_choreography import CUES

    run_id = "RUN-ACME-V2-001"
    correlation_id = "CORR-ACME-V2-001"
    incident_id = "INC-ACME-SAN-P1"
    route_by_service = {
        "grafana": "{origin}/d/{dashboard_uid}/{slug_redacted}",
        "n8n": "{origin}/{workflow_route_redacted}/executions/{event_ref}",
        "glpi": "{origin}/front/ticket.form.php?{id_redacted}",
    }
    checkpoints = {}
    filenames = []
    origin_time = datetime(2026, 10, 27, 8, 0, 0, tzinfo=timezone.utc)
    capture_time = datetime(2026, 10, 27, 8, 0, 10, tzinfo=timezone.utc)
    for index, cue in enumerate(CUES):
        event_ref = "EVENT-" + str(index + 100)
        ticket_id = "GLPI-12345" if cue.cue in {
            "ticket", "approve", "simulate", "verify", "close"
        } else None
        event_timestamp = (
            None if cue.cue == "enrich"
            else (origin_time + timedelta(seconds=index)).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        checkpoints[cue.cue] = {
            "event_ref": event_ref,
            "ticket_id": ticket_id,
            "event_timestamp_utc": event_timestamp,
        }
        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes([0, index, 0, 0])))
            + chunk(b"IEND")
        )
        (root / (cue.cue + ".png")).write_bytes(png_bytes)
        stamp = (capture_time + timedelta(seconds=index)).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest = {
            "schema": "star-browser-evidence/v2",
            "cue": cue.cue, "service": cue.service, "view": cue.view,
            "run_id": run_id, "correlation_id": correlation_id, "event_ref": event_ref,
            "incident_id": incident_id, "ticket_id": ticket_id,
            "event_timestamp_utc": event_timestamp,
            "expected_state": cue.required_state, "observed_state": cue.required_state,
            "captured_at": stamp,
            "sha256": hashlib.sha256(png_bytes).hexdigest(),
            "screenshot_file": cue.cue + ".png",
            "provenance": "ISOLATED_TEST_FIXTURE",
            "capture_transport": "LOCAL_HTML_FIXTURE_NO_HTTP",
            "anonymization": "SELECTOR_MASKS_UNREVIEWED",
            "qualification": "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF",
            "source_url_redacted": route_by_service[cue.service],
            "event_time_alignment": (
                "UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP"
                if event_timestamp is None
                else "MATCHED_TO_DECLARED_EVENT_TIMESTAMP_NOT_AUTHENTICATED"
            ),
            "runtime_page_authenticated": False,
            "business_outcome_verified": False,
            "human_approval_authenticated": False,
        }
        (root / (cue.cue + ".json")).write_text(
            json.dumps(manifest, sort_keys=True), encoding="utf-8"
        )
        filenames.append(cue.cue + ".json")
    expected = {
        "schema": "star-canonical-checkpoint-context/v1",
        "run_id": run_id, "correlation_id": correlation_id,
        "incident_id": incident_id, "checkpoints": checkpoints,
    }
    return expected, filenames


class BrowserManifestGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "detect.png").write_bytes(PNG)
        self.item = {"schema": "star-browser-evidence/v1", "cue": "detect", "service": "grafana",
                     "view": "alert_dashboard", "run_id": "RUN-ACME-001", "correlation_id": "CORR-ACME-001",
                     "event_ref": "DASH-7", "expected_state": "firing", "observed_state": "firing",
                     "captured_at": "2026-10-23T11:00:00+00:00", "sha256": hashlib.sha256(PNG).hexdigest(),
                     "screenshot_file": "detect.png", "provenance": "ISOLATED_TEST_FIXTURE",
                     "capture_transport": "LOCAL_HTML_FIXTURE_NO_HTTP",
                     "source_url_redacted": "{origin}/d/{dashboard_uid}/{slug_redacted}",
                     "event_time_alignment": "UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP",
                     "anonymization": "SELECTOR_MASKS_UNREVIEWED",
                     "qualification": "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF"}
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        (self.root / "detect.json").write_text(json.dumps(self.item), encoding="utf-8")

    def run_gate(self):
        return verify_browser_manifests(self.root, EXPECTED, ["detect.json"])

    def test_fixture_remains_simulated_and_storyboard_compatible(self):
        report = self.run_gate()
        self.assertEqual(report["entries"][0]["status"], "simulated")
        self.assertFalse(report["runtime_authenticated"])
        self.assertFalse(report["integrity_checked"])
        frames = storyboard(report, "SAN_FABRIC_P1")["frames"]
        self.assertEqual(frames[0]["capture_status"], "simulated")
        self.assertEqual(frames[1]["capture_status"], "missing")

    def test_complete_mode_refuses_partial_canonical_map(self):
        with self.assertRaisesRegex(ValueError, "all canonical checkpoints"):
            verify_browser_manifests(self.root, EXPECTED, ["detect.json"], require_complete=True)

    def test_complete_mode_refuses_nine_expected_with_one_capture(self):
        from demo.star_snapshot_choreography import CUES
        canonical = {**EXPECTED, "events": {cue.cue: "EVENT-" + str(i + 100) for i, cue in enumerate(CUES)}}
        with self.assertRaisesRegex(ValueError, "all canonical checkpoints"):
            verify_browser_manifests(self.root, canonical, ["detect.json"], require_complete=True)

    def test_complete_nine_cues_integrates_png_and_identity_gate(self):
        from datetime import datetime, timedelta, timezone
        from demo.star_snapshot_choreography import CUES
        routes = {
            "grafana": "{origin}/d/{dashboard_uid}/{slug_redacted}",
            "n8n": "{origin}/{workflow_route_redacted}/executions/{event_ref}",
            "glpi": "{origin}/front/ticket.form.php?{id_redacted}",
        }
        refs = {}
        names = []
        for index, cue in enumerate(CUES):
            event_ref = "EVENT-" + str(index + 100)
            refs[cue.cue] = event_ref
            # Each synthetic image is distinct; hash reuse must never pass.
            png = (b"\x89PNG\r\n\x1a\n" +
                   chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
                   chunk(b"IDAT", zlib.compress(bytes([0, index, 0, 0]))) + chunk(b"IEND"))
            (self.root / (cue.cue + ".png")).write_bytes(png)
            item = {**self.item, "cue": cue.cue, "service": cue.service,
                    "view": cue.view, "event_ref": event_ref,
                    "expected_state": cue.required_state, "observed_state": cue.required_state,
                    "screenshot_file": cue.cue + ".png", "sha256": hashlib.sha256(png).hexdigest(),
                    "source_url_redacted": routes[cue.service],
                    "runtime_page_authenticated": False, "business_outcome_verified": False,
                    "human_approval_authenticated": False,
                    "captured_at": (datetime(2026, 10, 23, 11, tzinfo=timezone.utc) +
                                    timedelta(seconds=index)).isoformat()}
            (self.root / (cue.cue + ".json")).write_text(json.dumps(item), encoding="utf-8")
            names.append(cue.cue + ".json")
        canonical = {**EXPECTED, "events": refs}
        report = verify_browser_manifests(self.root, canonical, names, require_complete=True)
        with_digests = verify_browser_manifests(
            self.root, canonical, names, require_complete=True,
            include_manifest_digests=True)
        self.assertEqual(report["capture_set_sha256"], with_digests["capture_set_sha256"])
        self.assertEqual(len(report["entries"]), 9)
        self.assertTrue(all(e["status"] == "simulated" for e in report["entries"]))
        self.assertFalse(report["runtime_authenticated"])
        self.assertFalse(report["integrity_checked"])
        self.assertRegex(report["capture_set_sha256"], r"^[0-9a-f]{64}$")
        # The independent replay pin must be provided explicitly; a matching
        # fixture is still simulated and requires an explicit fixture flag.
        with self.assertRaisesRegex(ValueError, "synthetic fixture"):
            verify_pinned_replay_captures(self.root, canonical, names, report["capture_set_sha256"])
        pinned = verify_pinned_replay_captures(
            self.root, canonical, names, report["capture_set_sha256"],
            allow_synthetic_fixture=True)
        self.assertEqual(pinned["provenance"], "ISOLATED_TEST_FIXTURE")
        self.assertFalse(pinned["runtime_authenticated"])
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_pinned_replay_captures(
                self.root, canonical, names, "b" * 64, allow_synthetic_fixture=True)
        # Input manifest ordering must not affect the canonical replay digest.
        reversed_report = verify_browser_manifests(
            self.root, canonical, list(reversed(names)), require_complete=True)
        self.assertEqual(report["capture_set_sha256"], reversed_report["capture_set_sha256"])
        # A new capture timestamp changes the digest even when image bytes match.
        changed = json.loads((self.root / "close.json").read_text())
        changed["captured_at"] = "2026-10-23T11:00:30+00:00"
        (self.root / "close.json").write_text(json.dumps(changed), encoding="utf-8")
        updated_report = verify_browser_manifests(self.root, canonical, names, require_complete=True)
        self.assertNotEqual(report["capture_set_sha256"], updated_report["capture_set_sha256"])
        # A timestamp-only change must invalidate the previously retained pin.
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_pinned_replay_captures(
                self.root, canonical, names, report["capture_set_sha256"],
                allow_synthetic_fixture=True)
        # A missing explicit false attestation is rejected by strict reconciliation.
        tampered = json.loads((self.root / "detect.json").read_text())
        del tampered["runtime_page_authenticated"]
        (self.root / "detect.json").write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "attestation"):
            verify_browser_manifests(self.root, canonical, names, require_complete=True)

    def test_optional_manifest_bytes_digest_matches_exact_input(self):
        plain = self.run_gate()
        verified = verify_browser_manifests(self.root, EXPECTED, ["detect.json"],
                                            include_manifest_digests=True)
        self.assertNotIn("manifest_sha256", plain["entries"][0])
        self.assertEqual(verified["entries"][0]["manifest_sha256"],
                         hashlib.sha256((self.root / "detect.json").read_bytes()).hexdigest())
        self.assertEqual(verified["entries"][0]["sha256"], plain["entries"][0]["sha256"])

    def test_invalid_manifest_digest_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "digest mode"):
            verify_browser_manifests(self.root, EXPECTED, ["detect.json"],
                                     include_manifest_digests=1)

    def test_operator_manifest_is_only_integrity_checked(self):
        self.item["provenance"] = "OPERATOR_BROWSER_UNREVIEWED"
        self.item["capture_transport"] = "READ_ONLY_BROWSER_HTTP_GET"
        self.write()
        report = self.run_gate()
        self.assertEqual(report["entries"][0]["status"], "integrity_checked")
        self.assertFalse(report["runtime_authenticated"])

    def test_identity_conflicts_rejected(self):
        for key in ("run_id", "correlation_id", "event_ref"):
            with self.subTest(key=key):
                old = self.item[key]
                self.item[key] = "WRONG-123"
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
                self.item[key] = old

    def test_claims_tampering_and_state_rejected(self):
        for key, value in (("sha256", "0" * 64), ("observed_state", "recovered"),
                           ("business_validated", True), ("verified_real_capture", True),
                           ("anonymization", "VERIFIED")):
            with self.subTest(key=key):
                old = self.item.get(key)
                self.item[key] = value
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
                if old is None:
                    self.item.pop(key)
                else:
                    self.item[key] = old

    def test_paths_and_symlinks_rejected(self):
        for name in ("../detect.png", "/tmp/detect.png", "sub/detect.png"):
            with self.subTest(name=name):
                self.item["screenshot_file"] = name
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
        self.item["screenshot_file"] = "link.png"
        (self.root / "link.png").symlink_to(self.root / "detect.png")
        self.write()
        with self.assertRaises(ValueError):
            self.run_gate()

    def test_missing_expected_identity_rejected(self):
        with self.assertRaises(ValueError):
            verify_browser_manifests(self.root, {**EXPECTED, "events": {}}, ["detect.json"])

    def test_duplicate_manifest_rejected(self):
        with self.assertRaises(ValueError):
            verify_browser_manifests(self.root, EXPECTED, ["detect.json", "detect.json"])

    def test_transport_contradiction_rejected(self):
        self.item["capture_transport"] = "READ_ONLY_BROWSER_HTTP_GET"
        self.write()
        with self.assertRaises(ValueError):
            self.run_gate()

    def test_unexpected_fields_and_unredacted_url_rejected(self):
        for key, value in (("secret", "do-not-publish"),
                           ("runtime_validated", True),
                           ("source_url_redacted", "http://localhost:8080/front/ticket.form.php?id=441"),
                           ("source_url_redacted", "{origin}/unexpected/path"),
                           ("event_time_alignment", "VERIFIED")):
            with self.subTest(key=key, value=value):
                original = self.item.get(key)
                self.item[key] = value
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
                if original is None:
                    self.item.pop(key)
                else:
                    self.item[key] = original
        self.write()
        self.assertEqual(self.run_gate()["entries"][0]["status"], "simulated")

    def test_required_provenance_fields_fail_closed(self):
        for field in ("source_url_redacted", "event_time_alignment"):
            with self.subTest(field=field):
                previous = self.item.pop(field)
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
                self.item[field] = previous

    def test_cross_service_redacted_route_rejected(self):
        for wrong_route in (
            "{origin}/front/ticket.form.php?{id_redacted}",
            "{origin}/{workflow_route_redacted}/executions/{event_ref}",
        ):
            with self.subTest(route=wrong_route):
                self.item["source_url_redacted"] = wrong_route
                self.write()
                with self.assertRaisesRegex(ValueError, "cross-service"):
                    self.run_gate()
        self.item["source_url_redacted"] = "{origin}/d/{dashboard_uid}/{slug_redacted}"

    def test_duplicate_json_keys_rejected_even_if_final_value_is_safe(self):
        self.write()
        manifest_path = self.root / "detect.json"
        raw = manifest_path.read_text()
        self.assertIn('"source_url_redacted"', raw)
        raw = raw.replace('"source_url_redacted":',
                          '"source_url_redacted": "http://evil.invalid/token", "source_url_redacted":', 1)
        manifest_path.write_text(raw)
        with self.assertRaisesRegex(ValueError, "duplicate capture manifest JSON key"):
            self.run_gate()

    def test_naive_timestamp_rejected(self):
        self.item["captured_at"] = "2026-10-23T11:00:00"
        self.write()
        with self.assertRaises(ValueError):
            self.run_gate()

    def test_malformed_api_and_manifest_field_shapes_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "canonical event contract"):
            verify_browser_manifests(self.root, [], ["detect.json"])
        with self.assertRaisesRegex(ValueError, "unsafe evidence root"):
            verify_browser_manifests(str(self.root), EXPECTED, ["detect.json"])
        with self.assertRaisesRegex(ValueError, "filename list"):
            verify_browser_manifests(self.root, EXPECTED, [[]])
        with self.assertRaisesRegex(ValueError, "complete-capture mode"):
            verify_browser_manifests(self.root, EXPECTED, ["detect.json"], require_complete=1)
        with self.assertRaisesRegex(ValueError, "invalid or missing expected event_ref"):
            verify_browser_manifests(
                self.root, {**EXPECTED, "events": {"detect": []}}, ["detect.json"])

        for key, value, message in (
            ("cue", [], "cue name"),
            ("service", {}, "capture service"),
            ("view", [], "application view"),
            ("provenance", [], "provenance"),
            ("event_ref", [], "observed event_ref"),
            ("captured_at", [], "timestamp"),
        ):
            with self.subTest(key=key):
                original = self.item.get(key)
                self.item[key] = value
                self.write()
                with self.assertRaisesRegex(ValueError, message):
                    self.run_gate()
                if original is None:
                    self.item.pop(key, None)
                else:
                    self.item[key] = original
        self.write()
        self.assertEqual(self.run_gate()["entries"][0]["status"], "simulated")

    def test_manifest_reader_is_bounded_and_refuses_symlinks_nonfiles_and_bad_utf8(self):
        manifest = self.root / "detect.json"
        target = self.root / "target.json"
        target.write_text(json.dumps(self.item), encoding="utf-8")
        manifest.unlink()
        manifest.symlink_to(target.name)
        with self.assertRaisesRegex(ValueError, "safely"):
            self.run_gate()
        manifest.unlink()
        self.write()

        manifest.write_bytes(b"x" * 16_385)
        with self.assertRaisesRegex(ValueError, "oversized"):
            self.run_gate()
        manifest.write_bytes(b"\xff")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            self.run_gate()

        manifest.unlink()
        manifest.mkdir()
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.run_gate()
        manifest.rmdir()
        self.write()

    def test_cue_order_chronology_rejected_even_when_input_reversed(self):
        other_png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND"))
        (self.root / "verify.png").write_bytes(other_png)
        other = {**self.item, "cue": "verify", "view": "recovery_dashboard",
                 "expected_state": "recovered", "observed_state": "recovered",
                 "event_ref": "DASH-8", "screenshot_file": "verify.png",
                 "sha256": hashlib.sha256(other_png).hexdigest(),
                 "captured_at": "2026-10-23T10:00:00+00:00"}
        (self.root / "verify.json").write_text(json.dumps(other), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "chronology"):
            verify_browser_manifests(self.root, {**EXPECTED, "events": {"detect": "DASH-7", "verify": "DASH-8"}},
                                     ["verify.json", "detect.json"])



    def test_v2_context_binds_run_incident_ticket_event_time_and_png(self):
        expected, names = _build_v2_capture_set(self.root)
        report = verify_browser_manifests(self.root, expected, names, require_complete=True)
        self.assertEqual(report["schema"], "star-capture-evidence-v1")
        self.assertEqual(report["context_schema"], "star-canonical-checkpoint-context/v1")
        self.assertEqual(report["run_id"], expected["run_id"])
        self.assertEqual(report["incident_id"], expected["incident_id"])
        self.assertEqual(report["checkpoint_context_count"], 9)
        self.assertEqual(report["event_timestamps_present"], 8)
        self.assertEqual(report["event_timestamps_absent"], 1)
        self.assertIs(report["runtime_attested"], False)
        self.assertIs(report["runtime_authenticated"], False)
        self.assertEqual(len(report["entries"]), 9)
        by_cue = {entry["cue"]: entry for entry in report["entries"]}
        self.assertIsNone(by_cue["detect"]["ticket_id"])
        self.assertEqual(by_cue["ticket"]["ticket_id"], "GLPI-12345")
        self.assertIsNone(by_cue["enrich"]["event_timestamp_utc"])
        self.assertFalse(by_cue["enrich"]["event_timestamp_present"])
        self.assertRegex(report["capture_set_sha256"], r"^[a-f0-9]{64}$")

    def test_v2_context_rejects_missing_or_contradictory_incident_ticket_and_time(self):
        mutations = (
            ("ticket", "incident_id", "INC-OTHER-001", "incident_id"),
            ("ticket", "ticket_id", "GLPI-99999", "ticket_id"),
            ("ticket", "event_timestamp_utc", "2026-10-27T08:01:00Z", "timestamp"),
        )
        for cue, field, value, message in mutations:
            with self.subTest(field=field):
                expected, names = _build_v2_capture_set(self.root)
                path = self.root / (cue + ".json")
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest[field] = value
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    verify_browser_manifests(self.root, expected, names, require_complete=True)
        expected, names = _build_v2_capture_set(self.root)
        path = self.root / "enrich.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        del manifest["event_timestamp_utc"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing checkpoint context"):
            verify_browser_manifests(self.root, expected, names, require_complete=True)

    def test_v2_ticket_cannot_be_fabricated_before_ticket_checkpoint(self):
        expected, names = _build_v2_capture_set(self.root)
        path = self.root / "detect.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["ticket_id"] = "GLPI-12345"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ticket_id mismatch"):
            verify_browser_manifests(self.root, expected, names, require_complete=True)

    def test_v2_context_must_use_canonical_utc_timestamp_and_valid_ticket_id(self):
        expected, names = _build_v2_capture_set(self.root)
        expected["checkpoints"]["detect"]["event_timestamp_utc"] = "2026-10-27T10:00:10+02:00"
        with self.assertRaisesRegex(ValueError, "canonical event timestamp"):
            verify_browser_manifests(self.root, expected, names, require_complete=True)
        expected, names = _build_v2_capture_set(self.root)
        expected["checkpoints"]["ticket"]["ticket_id"] = "../GLPI-12345"
        with self.assertRaisesRegex(ValueError, "invalid checkpoint ticket_id"):
            verify_browser_manifests(self.root, expected, names, require_complete=True)

    def test_v2_capture_set_digest_changes_when_declared_event_time_changes(self):
        expected, names = _build_v2_capture_set(self.root)
        first = verify_browser_manifests(
            self.root, expected, names, require_complete=True
        )["capture_set_sha256"]
        path = self.root / "detect.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["event_timestamp_utc"] = "2026-10-27T08:00:05Z"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        expected["checkpoints"]["detect"]["event_timestamp_utc"] = "2026-10-27T08:00:05Z"
        second = verify_browser_manifests(
            self.root, expected, names, require_complete=True
        )["capture_set_sha256"]
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
