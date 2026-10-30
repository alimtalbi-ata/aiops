"""Offline integration/mocks only; no Core/GLPI network or credentials."""
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.acme_evidence_utc_preflight import evidence_timestamps_valid, preflight_then_join

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
LEDGER = {"schema": "aiops.demo-ledger-read.v1", "evidence_refs": [
    {"evidence_id": "EVD-synthetic", "known_at": "2026-10-29T16:00:00+00:00"}
]}


class OfflineMockEvidencePreflightTests(unittest.TestCase):
    def _run(self, value):
        ledger = copy.deepcopy(LEDGER)
        ledger["evidence_refs"][0]["known_at"] = value
        core_get, glpi_get = Mock(), Mock()

        def joined_read():
            core_get()
            glpi_get()
            return {"state": "UNKNOWN", "ticket_id": None,
                    "evidence_verification": "UNKNOWN"}

        result = preflight_then_join(ledger, join_read_only=joined_read, now=NOW)
        return result, core_get, glpi_get

    def test_invalid_timestamps_short_circuit_before_core_and_glpi_get(self):
        for value in (
            None, 42, "", "2026-10-29", "2026-10-29T16:00:00",
            "2026-10-29T16:00:00+00:00garbage", "2026-13-29T16:00:00Z",
            "2026-10-29 16:00:00Z", "2026-10-30T12:06:00Z",
            "0001-01-01T00:00:00+14:00",
            "9999-12-31T23:59:59-14:00",
            "9999-12-31T23:59:59+00:00",
            "2026-10-29T16:00:00+99:99",
        ):
            with self.subTest(value=value):
                result, core_get, glpi_get = self._run(value)
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIsNone(result["ticket_id"])
                self.assertIsNone(result["incident_id"])
                self.assertIsNone(result["run_id"])
                self.assertEqual(result["evidence_ids"], [])
                core_get.assert_not_called()
                glpi_get.assert_not_called()

    def test_valid_aware_timestamp_allows_injected_read_only_join_only(self):
        for value in ("2026-10-29T16:00:00Z", "2026-10-29T18:00:00+02:00"):
            with self.subTest(value=value):
                result, core_get, glpi_get = self._run(value)
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIsNone(result["ticket_id"])
                core_get.assert_called_once_with()
                glpi_get.assert_called_once_with()

    def test_invalid_ledger_structure_never_invokes_join(self):
        for ledger in (None, {}, {"schema": "wrong", "evidence_refs": []},
                       {"schema": "aiops.demo-ledger-read.v1", "evidence_refs": []},
                       {"schema": "aiops.demo-ledger-read.v1", "evidence_refs": [None]},
                       {"schema": "aiops.demo-ledger-read.v1", "evidence_refs": [
                           {"known_at": "2026-10-29T16:00:00Z"}, {"known_at": "bad"}]},):
            with self.subTest(ledger=ledger):
                join = Mock()
                result = preflight_then_join(ledger, join_read_only=join, now=NOW)
                self.assertEqual(result["state"], "UNKNOWN")
                join.assert_not_called()

    def test_join_failure_is_unknown_not_a_fabricated_ticket(self):
        join = Mock(side_effect=ConnectionError("offline"))
        result = preflight_then_join(LEDGER, join_read_only=join, now=NOW)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["ticket_id"])
        self.assertEqual(result["verified_evidence_ids"], [])
        join.assert_called_once_with()

    def test_preflight_does_not_mutate_ledger(self):
        before = copy.deepcopy(LEDGER)
        self.assertTrue(evidence_timestamps_valid(LEDGER, now=NOW))
        self.assertEqual(LEDGER, before)


if __name__ == "__main__":
    unittest.main()
