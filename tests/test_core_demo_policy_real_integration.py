"""Real Core HTTP + PostgreSQL integration for the DEMO Policy observation.

CI-only synthetic rows in an ephemeral database; no mocks, Temporal, LIVE
command, tenant runtime authorization, or production connection.
"""
import os
import unittest

import psycopg
import requests
from psycopg.types.json import Jsonb

BASE = "http://127.0.0.1:1810"
TOKEN = os.environ["AIOPS_INTERNAL_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
PREFIX = "CI-DEMO-POLICY-"


class DemoPolicyCoreRealIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {
            "BLOCKED": ("DEMO", "BLOCKED", True, {}, None),
            "RESOLVED": ("DEMO", "RESOLVED", True, {}, ("PASS", "SIMULATE")),
            "RUNNING": ("DEMO", "RUNNING", True, {}, None),
            "RESOLVED-NOGATE": ("DEMO", "RESOLVED", True, {}, None),
            "UNKNOWN-GATE": ("DEMO", "BLOCKED", True, {}, ("UNKNOWN", "HUMAN_APPROVAL")),
            "FORGED-GATE": ("DEMO", "RESOLVED", True, {}, ("PASS", "ALLOW")),
            "GATE-BEFORE-RUN": ("DEMO", "RESOLVED", True, {}, ("PASS", "SIMULATE")),
            "GATE-IN-FUTURE": ("DEMO", "RESOLVED", True, {}, ("PASS", "SIMULATE")),
            "RUN-IN-FUTURE": ("DEMO", "RUNNING", True, {}, None),
            "LIVE": ("LIVE", "RESOLVED", True, {}, None),
            "OBSERVED": ("DEMO", "RESOLVED", False, {}, None),
            "TENANT": ("DEMO", "BLOCKED", True,
                       {"metadata": {"ownerTenantId": "PRIVATE-CI-TENANT"}}, None),
        }
        with psycopg.connect(DATABASE_URL) as c:
            for suffix, (mode, status, synthetic, payload, gate) in cls.cases.items():
                rid, iid = "RUN-" + PREFIX + suffix, "INC-" + PREFIX + suffix
                c.execute(
                    "insert into aiops.incidents(incident_id,external_id,title,severity,"
                    "state,opened_at,source,synthetic,payload) "
                    "values(%s,%s,'Ephemeral CI synthetic observation','P1',"
                    "'OPEN',now(),'ci',%s,%s)",
                    (iid, PREFIX + suffix, synthetic, Jsonb(payload)),
                )
                c.execute(
                    "insert into aiops.runs(run_id,incident_id,mode,scenario_id,"
                    "status,idempotency_key) values(%s,%s,%s,'CI-ACME',%s,%s)",
                    (rid, iid, mode, status, PREFIX + suffix.lower()),
                )
                if gate:
                    c.execute(
                        "insert into aiops.gates(gate_id,run_id,stage,state,decision,reason)"
                        " values(%s,%s,'POLICY',%s,%s,'ephemeral CI record')",
                        ("GATE-" + PREFIX + suffix, rid, gate[0], gate[1]),
                    )
            c.execute(
                "update aiops.gates set evaluated_at = "
                "(select created_at - interval '1 second' from aiops.runs "
                "where run_id=%s) where run_id=%s",
                ("RUN-" + PREFIX + "GATE-BEFORE-RUN",
                 "RUN-" + PREFIX + "GATE-BEFORE-RUN"),
            )
            c.execute(
                "update aiops.gates set evaluated_at = now() + interval '1 day' "
                "where run_id=%s",
                ("RUN-" + PREFIX + "GATE-IN-FUTURE",),
            )
            c.execute(
                "update aiops.runs set created_at = now() + interval '1 day' "
                "where run_id=%s",
                ("RUN-" + PREFIX + "RUN-IN-FUTURE",),
            )

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(DATABASE_URL) as c:
            c.execute("delete from aiops.gates where run_id like %s", ("RUN-" + PREFIX + "%",))
            c.execute("delete from aiops.runs where run_id like %s", ("RUN-" + PREFIX + "%",))
            c.execute("delete from aiops.incidents where incident_id like %s",
                      ("INC-" + PREFIX + "%",))

    def read(self, suffix, token=TOKEN):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        return requests.get(BASE + "/api/noc/runs/RUN-" + PREFIX + suffix +
                            "/policy-status", headers=headers, timeout=3,
                            allow_redirects=False)

    def test_resolved_with_recorded_simulate_is_never_live_proof(self):
        response = self.read("RESOLVED")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()
        self.assertEqual(data["schema"], "aiops.core-demo-policy-observation.v1")
        self.assertEqual(data["run_id"], "RUN-" + PREFIX + "RESOLVED")
        self.assertEqual(data["incident_id"], "INC-" + PREFIX + "RESOLVED")
        self.assertEqual(data["run_status"], "RESOLVED")
        self.assertEqual((data["policy_gate_state"], data["policy_decision"]),
                         ("PASS", "SIMULATE"))
        self.assertEqual(data["explanation_code"], "RESOLVED_WITH_SIMULATE_GATE_NOT_LIVE")
        self.assertTrue(data["policy_gate_recorded"])
        for key in ("runtime_attested", "policy_http_verified", "hitl_approval_verified",
                    "temporal_execution_verified", "postchecks_verified",
                    "rollback_verified", "tenant_acl_qualified",
                    "live_remediation_authorized"):
            self.assertIs(data[key], False, key)
        self.assertNotIn("ephemeral CI record", response.text)

    def test_blocked_without_gate_is_missing_not_causal_explanation(self):
        response = self.read("BLOCKED")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["run_status"], "BLOCKED")
        self.assertEqual(data["policy_gate_state"], "MISSING")
        self.assertIsNone(data["policy_decision"])
        self.assertIs(data["policy_gate_recorded"], False)
        self.assertEqual(data["explanation_code"], "BLOCKED_WITHOUT_POLICY_GATE")

    def test_running_and_resolved_without_gate_remain_unverified(self):
        for suffix, code in (
            ("RUNNING", "RUNNING_NO_TERMINAL_PROOF"),
            ("RESOLVED-NOGATE", "RESOLVED_POLICY_SIMULATION_UNVERIFIED"),
        ):
            with self.subTest(suffix=suffix):
                response = self.read(suffix)
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["explanation_code"], code)
                self.assertEqual(data["policy_gate_state"], "MISSING")
                self.assertIs(data["temporal_execution_verified"], False)

    def test_persisted_unknown_gate_does_not_become_simulate(self):
        response = self.read("UNKNOWN-GATE")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["policy_gate_state"], "UNKNOWN")
        self.assertEqual(data["policy_decision"], "HUMAN_APPROVAL")
        self.assertEqual(data["explanation_code"], "BLOCKED_CAUSE_NOT_ESTABLISHED")
        self.assertIs(data["live_remediation_authorized"], False)

    def test_inconsistent_gate_is_rejected_even_when_run_is_resolved(self):
        response = self.read("FORGED-GATE")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json(), {"detail": "demo_policy_observation_unavailable"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("ALLOW", response.text)

    def test_impossible_run_or_gate_chronology_is_rejected(self):
        # Actual Core HTTP and PostgreSQL timestamptz, not a mock Policy server.
        for suffix in ("GATE-BEFORE-RUN", "GATE-IN-FUTURE", "RUN-IN-FUTURE"):
            with self.subTest(suffix=suffix):
                response = self.read(suffix)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.json(),
                                 {"detail": "demo_policy_observation_unavailable"})
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn("SIMULATE", response.text)
                self.assertNotIn("RUN-" + PREFIX, response.text)

    def test_live_observed_tenant_and_missing_run_are_denied(self):
        for suffix in ("LIVE", "OBSERVED", "TENANT", "MISSING", "BAD!ID"):
            with self.subTest(suffix=suffix):
                response = self.read(suffix)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn("PRIVATE-CI-TENANT", response.text)
                self.assertNotIn("RUN-" + PREFIX, response.text)

    def test_missing_and_forged_bearer_are_rejected(self):
        for token in (None, "", "invalid", TOKEN + " extra"):
            with self.subTest(token=repr(token)):
                response = self.read("RESOLVED", token=token)
                self.assertEqual(response.status_code, 401, response.text)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn("RUN-" + PREFIX, response.text)


if __name__ == "__main__":
    unittest.main()
