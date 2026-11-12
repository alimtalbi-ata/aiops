"""Offline *contract/mocks* only; no real Core, GLPI or tenant ACL."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from shared.core_itsm_xref_read import CoreRead, SCHEMA, resolve_ticket_run

NOW = datetime(2026, 10, 30, 14, 45, tzinfo=timezone.utc)
TENANT = "TEN-DEMO"
INSTANCE = "GLPI-DEMO"
TICKET = "1234"
RUN = "RUN-DEMO_123"
INC = "INC-DEMO_123"


def stamp(delta=0):
    return (NOW + timedelta(seconds=delta)).isoformat().replace("+00:00", "Z")


def fixture(**changes):
    body = {"schema": SCHEMA, "status": "VERIFIED", "tenant_id": TENANT,
            "glpi_instance_id": INSTANCE, "ticket_id": TICKET,
            "incident_id": INC, "run_id": RUN,
            "source_system": "GLPI", "source_event_id": "EVT-XREF-001",
            "association_id": "XREF-001", "mapping_version": 1,
            "verification_method": "AUTHENTICATED_ID_READBACK",
            "tenant_acl_qualified": True, "glpi_ticket_readback_verified": True,
            "core_run_readback_verified": True,
            "observed_at": stamp(-15), "known_at": stamp(-10),
            "provenance": "AUTHENTICATED_SOURCE_API"}
    body.update(changes)
    return body


def call(get=None, **changes):
    params = dict(tenant_id=TENANT, tenant_authenticated=True,
                  tenant_acl_qualified=True, glpi_instance_id=INSTANCE,
                  ticket_id=TICKET, expected_incident_id=INC,
                  expected_run_id=RUN, evidence_known_at=stamp(-20), now=NOW,
                  core_get=get)
    params.update(changes)
    return resolve_ticket_run(**params)


class CoreXrefReadContractTests(unittest.TestCase):
    def assert_hidden(self, out):
        self.assertIsNone(out["run_id"])
        self.assertIsNone(out["incident_id"])
        self.assertIsNone(out["ticket_id"])
        self.assertIsNone(out["evidence_id"])
        self.assertEqual(out["verified_evidence_ids"], [])

    def test_verified_core_readback_mock_only(self):
        get = Mock(return_value=CoreRead(200, fixture(), True, True))
        out = call(get)
        self.assertEqual(out["link_status"], "VERIFIED")
        self.assertEqual(out["connection_state"], "CONNECTED")
        self.assertEqual(out["run_id"], RUN)
        self.assertEqual(out["incident_id"], INC)
        self.assertEqual(out["ticket_id"], TICKET)
        self.assert_hidden({**out, "run_id": None, "incident_id": None, "ticket_id": None})
        get.assert_called_once_with("/api/tenants/TEN-DEMO/itsm/glpi/GLPI-DEMO/tickets/1234/xref")

    def test_no_connector_installed_never_promotes(self):
        out = call()
        self.assertEqual(out["connection_state"], "NOT_INSTALLED")
        self.assert_hidden(out)

    def test_invalid_ids_and_tenant_never_call_core(self):
        changes = [
            {"tenant_id": "TEN/../other"}, {"tenant_authenticated": False},
            {"tenant_acl_qualified": False}, {"tenant_id": ""},
            {"ticket_id": "１２３"}, {"ticket_id": "0"},
            {"ticket_id": "12/../3"}, {"glpi_instance_id": "GLPI/other"},
            {"expected_run_id": "RUN-..%2f"}, {"expected_incident_id": "INC/foreign"},
            {"expected_run_id": "RUN-😈"},
        ]
        for change in changes:
            with self.subTest(change=change):
                get = Mock(return_value=CoreRead(200, fixture(), True, True))
                out = call(get, **change)
                self.assertEqual(out["link_status"], "UNKNOWN")
                self.assert_hidden(out)
                get.assert_not_called()

    def test_bad_evidence_utc_and_clock_never_call_core(self):
        changes = [
            {"evidence_known_at": "0001-01-01T00:00:00+02:00"},
            {"evidence_known_at": "2026-10-30T14:45:00"},
            {"evidence_known_at": "9999-12-31T23:59:59-23:59"},
            {"evidence_known_at": "2026-10-30T15:00:00Z"},
            {"evidence_known_at": "not a timestamp"},
            {"now": NOW.replace(tzinfo=None)},
            {"now": datetime(9999, 12, 31, tzinfo=timezone.utc)},
        ]
        for change in changes:
            with self.subTest(change=change):
                get = Mock(return_value=CoreRead(200, fixture(), True, True))
                out = call(get, **change)
                self.assertEqual(out["reason"], "UTC_PREFLIGHT_INVALID")
                self.assert_hidden(out)
                get.assert_not_called()

    def test_ticket_text_run_id_is_not_a_mapping(self):
        # Even a unique RUN token in GLPI text is not passed to this API.
        get = Mock(return_value=CoreRead(200, {"schema": SCHEMA, "status": "UNKNOWN",
                                               "title": "please use " + RUN}, True, True))
        out = call(get)
        self.assertEqual(out["link_status"], "UNKNOWN")
        self.assert_hidden(out)

    def test_forged_or_copied_run_is_not_verified(self):
        for change in ({"run_id": "RUN-FORGED"}, {"incident_id": "INC-OTHER"},
                       {"ticket_id": "9999"}, {"glpi_instance_id": "GLPI-OTHER"}):
            with self.subTest(change=change):
                out = call(Mock(return_value=CoreRead(200, fixture(**change), True, True)))
                self.assertEqual(out["link_status"], "UNKNOWN")
                self.assert_hidden(out)

    def test_cross_tenant_denied(self):
        out = call(Mock(return_value=CoreRead(200, fixture(tenant_id="TEN-OTHER"), True, True)))
        self.assertEqual(out["link_status"], "UNAUTHORIZED")
        self.assert_hidden(out)

    def test_conflict_cannot_be_borrowed_from_other_ticket(self):
        out = call(Mock(return_value=CoreRead(200, fixture(status="CONFLICT", ticket_id="9999"), True, True)))
        self.assertEqual(out["link_status"], "UNKNOWN")
        self.assert_hidden(out)

    def test_unauthorized_401_403(self):
        for code in (401, 403):
            with self.subTest(code=code):
                out = call(Mock(return_value=CoreRead(code)))
                self.assertEqual(out["connection_state"], "UNAUTHORIZED")
                self.assert_hidden(out)

    def test_unavailable_5xx_and_exception(self):
        for get in (Mock(return_value=CoreRead(503)), Mock(side_effect=TimeoutError)):
            out = call(get)
            self.assertEqual(out["connection_state"], "UNAVAILABLE")
            self.assert_hidden(out)

    def test_404_is_unknown_not_connected_link(self):
        out = call(Mock(return_value=CoreRead(404, authenticated=True, tenant_acl_checked=True)))
        self.assertEqual(out["connection_state"], "CONNECTED")
        self.assertEqual(out["link_status"], "UNKNOWN")
        self.assert_hidden(out)

    def test_core_connected_is_not_linked(self):
        out = call(Mock(return_value=CoreRead(200, fixture(status="CONNECTED"), True, True)))
        self.assertEqual(out["connection_state"], "CONNECTED")
        self.assertEqual(out["link_status"], "UNKNOWN")
        self.assert_hidden(out)

    def test_transport_auth_and_acl_required(self):
        for authenticated, scoped in ((False, True), (True, False), (False, False)):
            with self.subTest(authenticated=authenticated, scoped=scoped):
                out = call(Mock(return_value=CoreRead(200, fixture(), authenticated, scoped)))
                self.assertEqual(out["link_status"], "UNAUTHORIZED")
                self.assert_hidden(out)

    def test_stale_conflict_and_clock_disagreement(self):
        cases = [(fixture(status="STALE"), "STALE"),
                 (fixture(status="CONFLICT"), "CONFLICT"),
                 (fixture(observed_at=stamp(-700)), "STALE"),
                 (fixture(known_at=stamp(-700)), "CONFLICT"),
                 (fixture(known_at=stamp(700)), "CONFLICT")]
        for body, status in cases:
            with self.subTest(body=body):
                out = call(Mock(return_value=CoreRead(200, body, True, True)))
                self.assertEqual(out["link_status"], status)
                self.assert_hidden(out)

    def test_evidence_freshness_fails_closed_before_core_get(self):
        # The injectable transport receives only the path, not the Evidence
        # timestamp. An otherwise VERIFIED response cannot launder stale or
        # future Evidence through this client.
        for delta, status, reason in ((-301, "STALE", "EVIDENCE_STALE"),
                                      (1, "UNKNOWN", "UTC_PREFLIGHT_INVALID")):
            with self.subTest(delta=delta):
                get = Mock(return_value=CoreRead(200, fixture(), True, True))
                out = call(get, evidence_known_at=stamp(delta))
                self.assertEqual(out["link_status"], status)
                self.assertEqual(out["reason"], reason)
                self.assert_hidden(out)
                get.assert_not_called()
        get = Mock(return_value=CoreRead(200, fixture(), True, True))
        out = call(get, evidence_known_at=stamp(-300))
        self.assertEqual(out["link_status"], "VERIFIED")
        get.assert_called_once()

    def test_real_core_negative_readback_has_no_business_identifiers(self):
        # Core's actual 200 negative response is only {schema, status}.
        # It is not an authorization failure and must never expose a Run.
        for status, expected in (("STALE", "STALE"), ("CONFLICT", "CONFLICT"),
                                 ("UNKNOWN", "UNKNOWN")):
            with self.subTest(status=status):
                body = {"schema": SCHEMA, "status": status}
                out = call(Mock(return_value=CoreRead(200, body, True, True)))
                self.assertEqual(out["link_status"], expected)
                self.assertEqual(out["connection_state"], "CONNECTED")
                self.assert_hidden(out)

    def test_negative_readback_requires_transport_acl_and_rejects_wrong_scope(self):
        body = {"schema": SCHEMA, "status": "STALE"}
        for authenticated, scoped in ((False, True), (True, False)):
            with self.subTest(authenticated=authenticated, scoped=scoped):
                out = call(Mock(return_value=CoreRead(200, body, authenticated, scoped)))
                self.assertEqual(out["link_status"], "UNAUTHORIZED")
                self.assert_hidden(out)
        for field, value, expected in (("tenant_id", "TEN-OTHER", "UNAUTHORIZED"),
                                       ("glpi_instance_id", "GLPI-OTHER", "UNKNOWN"),
                                       ("ticket_id", "9999", "UNKNOWN")):
            with self.subTest(field=field):
                out = call(Mock(return_value=CoreRead(
                    200, {**body, field: value}, True, True)))
                self.assertEqual(out["link_status"], expected)
                self.assert_hidden(out)
        # A positive status without canonical IDs cannot become VERIFIED.
        out = call(Mock(return_value=CoreRead(
            200, {"schema": SCHEMA, "status": "VERIFIED"}, True, True)))
        self.assertNotEqual(out["link_status"], "VERIFIED")
        self.assert_hidden(out)

    def test_missing_or_forged_provenance_denied(self):
        cases = [{"source_event_id": None}, {"association_id": None},
                 {"mapping_version": True}, {"mapping_version": 0},
                 {"tenant_acl_qualified": False},
                 {"glpi_ticket_readback_verified": False},
                 {"core_run_readback_verified": False},
                 {"verification_method": "TITLE_MATCH"},
                 {"provenance": "SYNTHETIC_SEED"},
                 {"source_system": "COPILOT"}]
        for change in cases:
            with self.subTest(change=change):
                out = call(Mock(return_value=CoreRead(200, fixture(**change), True, True)))
                self.assertEqual(out["link_status"], "UNKNOWN")
                self.assert_hidden(out)

    def test_unexpected_nested_claims_rejected(self):
        out = call(Mock(return_value=CoreRead(200, fixture(tenant_context={"tenant_id": "TEN-OTHER"}), True, True)))
        self.assertEqual(out["link_status"], "UNKNOWN")
        self.assert_hidden(out)

    def test_invalid_core_timestamp_fails_closed(self):
        for change in ({"known_at": "0001-01-01T00:00:00Z"},
                       {"observed_at": "9999-12-31T23:59:59-12:00"},
                       {"known_at": "bad"}):
            with self.subTest(change=change):
                out = call(Mock(return_value=CoreRead(200, fixture(**change), True, True)))
                self.assertEqual(out["link_status"], "UNKNOWN")
                self.assert_hidden(out)


if __name__ == "__main__":
    unittest.main()
