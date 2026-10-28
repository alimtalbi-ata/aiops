"""Offline HMAC/identity contract tests; no Core/GLPI service is contacted."""
import hashlib
import hmac
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.acme_itsm_binding import correlate_acme_ticket, RECEIPT_SCHEMA

NOW = datetime(2026, 10, 28, 4, 30, tzinfo=timezone.utc)
KEY = b"test-only-synthetic-signing-key-32-bytes-minimum"
DIGEST = "a" * 64


def inputs():
    core = dict(schema="aiops.acme-golden-run-readback.v1", state="MATCHED_UNATTESTED",
                mode="DEMO", canonical_run_id="RUN-ACME-1",
                canonical_incident_id="INC-ACME-DEMO-SAN-001",
                scenario_id="SCN-GOLDEN-PAYMENT-P1", fixture_sha256=DIGEST,
                glpi_ticket_id=None, glpi_correlation="UNKNOWN", runtime_attested=False,
                production_qualified=False, live_remediation_authorized=False)
    glpi = dict(schema="aiops.glpi.ticket-observation.v1", state="OBSERVED_UNCORRELATED",
                source="AUTHENTICATED_GLPI_API_READ_NOT_ATTESTATION",
                correlation_state="UNKNOWN", incident_id=None, run_id=None,
                ticket_id="42", entity_id=7, response_sha256="b" * 64,
                read_at_utc="2026-10-28T04:29:30Z", runtime_attested=False,
                production_qualified=False, live_remediation_authorized=False)
    receipt = dict(schema=RECEIPT_SCHEMA, issuer="CANONICAL_CORE_ITSMLINK",
                   mode="DEMO", run_id="RUN-ACME-1", incident_id="INC-ACME-DEMO-SAN-001",
                   ticket_id="42", entity_id=7, fixture_sha256=DIGEST,
                   issued_at_utc="2026-10-28T04:29:00Z",
                   expires_at_utc="2026-10-28T04:33:00Z")
    return core, glpi, receipt


def check(core=None, glpi=None, receipt=None, key=KEY, raw=None,
          signature=None, now=NOW, scope=7):
    a, b, c = inputs()
    core = a if core is None else core
    glpi = b if glpi is None else glpi
    receipt = c if receipt is None else receipt
    raw = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode() if raw is None else raw
    signature = hmac.new(key, raw, hashlib.sha256).hexdigest() if signature is None else signature
    return correlate_acme_ticket(
        core, glpi, raw, signature, key, now=now,
        authorized_entity_id=scope)


class AcmeITSMBindingTests(unittest.TestCase):
    def assert_unknown(self, result):
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["glpi_ticket_id"])
        self.assertIsNone(result["canonical_run_id"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["live_remediation_authorized"])

    def test_matching_synthetic_contract_still_unattested(self):
        result = check()
        self.assertEqual(result["state"], "CONTRACT_MATCHED_UNATTESTED")
        self.assertEqual(result["glpi_ticket_id"], "42")
        self.assertEqual(result["canonical_run_id"], "RUN-ACME-1")
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["production_qualified"])
        self.assertFalse(result["live_remediation_authorized"])

    def test_core_identity_and_mode_fail_closed(self):
        for field, value in (("canonical_run_id", "RUN-other"),
                             ("canonical_incident_id", "INC-other"),
                             ("mode", "LIVE"), ("state", "UNKNOWN"),
                             ("scenario_id", "SCN-other"),
                             ("fixture_sha256", "c" * 64),
                             ("runtime_attested", True),
                             ("glpi_ticket_id", "42")):
            core, _, _ = inputs()
            core[field] = value
            with self.subTest(field=field):
                self.assert_unknown(check(core=core))

    def test_glpi_entity_ticket_and_provenance_fail_closed(self):
        for field, value in (("ticket_id", "43"), ("ticket_id", True),
                             ("entity_id", 8), ("entity_id", True),
                             ("state", "CORRELATED"), ("source", "BROWSER"),
                             ("correlation_state", "MATCHED"),
                             ("incident_id", "INC-ACME-DEMO-SAN-001"),
                             ("run_id", "RUN-ACME-1"),
                             ("response_sha256", "invalid")):
            _, glpi, _ = inputs()
            glpi[field] = value
            with self.subTest(field=field):
                self.assert_unknown(check(glpi=glpi))

    def test_receipt_mismatch_replay_and_live_fail_closed(self):
        for field, value in (("mode", "LIVE"), ("issuer", "BROWSER"),
                             ("ticket_id", "99"), ("entity_id", 8),
                             ("run_id", "RUN-OTHER"), ("incident_id", "INC-OTHER"),
                             ("fixture_sha256", "d" * 64),
                             ("expires_at_utc", "2026-10-28T04:29:00Z"),
                             ("issued_at_utc", "2026-10-28T04:31:00Z")):
            _, _, receipt = inputs()
            receipt[field] = value
            with self.subTest(field=field):
                self.assert_unknown(check(receipt=receipt))

    def test_signature_tampering_and_missing_key_fail_closed(self):
        self.assert_unknown(check(signature="0" * 64))
        self.assert_unknown(check(key=b"short"))
        self.assert_unknown(check(raw=b'{"schema":"a","schema":"b"}'))
        self.assert_unknown(check(raw=b'{"a":NaN}'))
        self.assert_unknown(check(raw=b"x" * 4097))
        self.assert_unknown(check(raw=b"\xff"))

    def test_expired_future_stale_and_naive_clock_fail_closed(self):
        self.assert_unknown(check(now=NOW + timedelta(minutes=6)))
        self.assert_unknown(check(now=NOW - timedelta(minutes=2)))
        self.assert_unknown(check(now=NOW.replace(tzinfo=None)))
        _, glpi, _ = inputs()
        glpi["read_at_utc"] = "2026-10-28T04:10:00Z"
        self.assert_unknown(check(glpi=glpi))

    def test_authorized_glpi_entity_scope_is_mandatory_and_strict(self):
        # The same valid signed receipt and GLPI observation must never cross
        # the independently authorized entity boundary.
        for scope in (None, True, False, "7", -1, 8, 2147483648, 7.0):
            with self.subTest(scope=scope):
                self.assert_unknown(check(scope=scope))
        self.assertEqual(check(scope=7)["state"], "CONTRACT_MATCHED_UNATTESTED")

    def test_replayed_matching_receipt_in_another_entity_is_rejected(self):
        _, glpi, receipt = inputs()
        glpi["entity_id"] = 8
        receipt["entity_id"] = 8
        self.assert_unknown(check(glpi=glpi, receipt=receipt, scope=7))
        # Still un-attested even when an independently authorized scope matches.
        matched = check(glpi=glpi, receipt=receipt, scope=8)
        self.assertEqual(matched["state"], "CONTRACT_MATCHED_UNATTESTED")
        self.assertFalse(matched["runtime_attested"])
        self.assertFalse(matched["live_remediation_authorized"])

    def test_untrusted_shapes_fail_closed_without_identifier_leak(self):
        for core, glpi in ((None, []), ([], {}), ({}, {}), ("evil", "evil")):
            with self.subTest(core=core):
                self.assert_unknown(check(core=core, glpi=glpi))
        _, _, receipt = inputs()
        receipt["untrusted_extra_field"] = "ignore-me"
        self.assert_unknown(check(receipt=receipt))

if __name__ == "__main__":
    unittest.main()
