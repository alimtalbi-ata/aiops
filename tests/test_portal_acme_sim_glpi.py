"""Portal ACME SIM-GLPI: independent Core sandbox GET, no human READ/READMY."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from fastapi.testclient import TestClient
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-acme-sim-internal"}):
    from portal import main, acme_sim_glpi

ATTEMPT = "ACME-SIM-ABCDEF1234567890"
TOKEN = "ci-acme-sim-viewer"
INTERNAL = "ci-acme-sim-internal"
URL = "http://aiops2-core:810/api/sandbox/acme/e2e/" + ATTEMPT
WORKER_URL = "http://aiops2-worker:815/api/sandbox/acme/e2e/" + ATTEMPT
ENV = {
    "AIOPS_PORTAL_READ_TOKEN": TOKEN,
    "AIOPS_INTERNAL_TOKEN": INTERNAL,
    "AIOPS_ACME_SANDBOX_ENABLED": "true",
    "CORE_URL": "http://aiops2-core:810",
    "WORKER_URL": "http://aiops2-worker:815",
}
GOOD = {
    "attempt_id": ATTEMPT, "tenant_id": "ACME-TEST",
    "scenario_id": "ACME-SAN-PAYMENTS", "mode": "SIMULATION",
    "source": "SYNTHETIC_SIMULATOR", "ticket_authority": "SIMULATED_ONLY",
    "ticket_id": "SIM-GLPI-ABCDEF1234567890",
    "ticket_status": "RESOLVED", "incident_status": "RESOLVED",
    "run_status": "RESOLVED", "incident_id": "INC-ACME-SIM-1234",
    "run_id": "RUN-ACME-SIM-1234", "analysis_validated": True,
    "critic_validated": True, "evidence_count": 2,
    "approval_issuer": "TWIN_ACME_SIMULATED",
    "human_approved": False, "live_effects_allowed": False,
    "real_glpi_writes_allowed": False,
    "human_approval_claimed": False, "execution_allowed": False,
    "effect_allowed": False, "glpi_mode": "SIMULATED_ONLY",
    "schema": "aiops.core-acme-sandbox-readback.v1",
    "proposal_id": "SIM-PROP-1234567890",
    "approval_id": "SIM-APP-1234567890",
    "source_event_count": 7, "source_hashes_qualified": True,
    "source_event_ids": ["SYN-EVT-" + str(i).zfill(8) for i in range(7)],
    "request_sha256": "a" * 64,
    "worker_receipt_verified": True,
    "resolution_after_worker_receipt": True,
    "approval_fresh_at_resolution": True,
    "approval_nonce_consumed": True,
    "approval_nonce_revoked": False,
}
WORKER = {
    "schema": "aiops.worker-acme-simulated-no-effect.v1",
    "attempt_id": ATTEMPT, "tenant_id": "ACME-TEST",
    "incident_id": GOOD["incident_id"], "run_id": GOOD["run_id"],
    "proposal_id": GOOD["proposal_id"], "approval_id": GOOD["approval_id"],
    "approval_issuer": "TWIN_ACME_SIMULATED", "approval_kind": "SIMULATED",
    "action": "SIMULATE", "receipt_status": "SIMULATED_NO_EFFECT",
    "receipt_phase": "PRE_RESOLUTION", "core_status_at_validation": "PREPARED",
    "resolution_verified": False, "post_resolution_readback_required": True,
    "audit_authority": "TEMPORAL_WORKFLOW_HISTORY_ONLY", "effect_receipts": 0,
    "human_approved": False, "execution_allowed": False, "effect_allowed": False,
    "live_effects_allowed": False, "real_glpi_writes_allowed": False,
    "core_014_015_written": False, "glpi_write": False,
    "audit_transitions": [
        "CORE_PREPARED_INDEPENDENTLY_VERIFIED",
        "TWIN_SIMULATED_APPROVAL_VALIDATED",
        "POLICY_SIMULATE_INDEPENDENTLY_VERIFIED",
        "WORKER_NO_EFFECT",
    ],
}


def upstream(value=None, code=200):
    response = Mock()
    response.status_code = code
    response.content = b'{"synthetic":true}'
    response.json.return_value = dict(GOOD if value is None else value)
    return response


def good_reads(core=None, worker=None):
    receipt = WORKER if worker is None else worker
    return [upstream(receipt), upstream(GOOD if core is None else core), upstream(receipt)]


class PortalSimulatedGlpiTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, ENV)
        self.environment.start()
        self.client = TestClient(main.app)
        # Controlled source-only fixture; production guard is always deny.
        self.actor_acl_fixture = patch.object(acme_sim_glpi, "_require_sim_actor_acl", return_value=True)
        self.actor_acl_fixture.start()

    def tearDown(self):
        self.client.close()
        self.actor_acl_fixture.stop()
        self.environment.stop()

    def get(self, attempt=ATTEMPT, authorized=True, **headers):
        h = {"Authorization": "Bearer " + TOKEN} if authorized else {}
        h.update(headers)
        return self.client.get("/api/demo/acme-sim-glpi/" + attempt, headers=h)

    def assert_security(self, response):
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def assert_unknown(self, response, code=503):
        self.assertEqual(response.status_code, code)
        data = response.json()
        self.assertIn(data["state"], ("UNKNOWN", "UNAUTHORIZED"))
        self.assertFalse(data["human_allow"])
        self.assertFalse(data["real_glpi_writes_allowed"])
        self.assertNotIn("ticket", data)
        self.assertNotIn("run_id", data)
        self.assert_security(response)

    def test_public_shell_has_simulated_badge_no_ids_and_inert_human_actions(self):
        with patch.object(acme_sim_glpi.requests, "get", side_effect=AssertionError("Core GET")):
            response = self.client.get("/demo/acme-sim-glpi")
        self.assertEqual(response.status_code, 200)
        self.assert_security(response)
        page = response.text
        self.assertIn('data-simulation-badge="SIMULATED"', page)
        self.assertIn("SIMULATED · SANDBOX ONLY", page)
        self.assertIn("SIM-GLPI-", page)
        self.assertIn('src="/assets/acme-sim-glpi.js"', page)
        self.assertEqual(page.count('disabled aria-disabled="true"'), 2)
        self.assertNotIn("SIM-GLPI-ABCDEF", page)
        self.assertIn("historique non attesté", page)
        link = self.client.get("/itsm")
        self.assertIn('href="/demo/acme-sim-glpi"', link.text)

    def test_no_viewer_no_core_business_get(self):
        for headers in ({}, {"Authorization": "Bearer bad"}, {"Authorization": "Basic " + TOKEN}):
            with self.subTest(headers=headers):
                with patch.object(acme_sim_glpi.requests, "get") as get:
                    response = self.client.get("/api/demo/acme-sim-glpi/" + ATTEMPT, headers=headers)
                self.assert_unknown(response, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                get.assert_not_called()

    def test_unconfigured_viewer_is_503_before_core(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            with patch.object(acme_sim_glpi.requests, "get") as get:
                response = self.get()
        self.assert_unknown(response)
        get.assert_not_called()

    def test_wrong_namespace_denied_without_upstream_even_if_viewer_valid(self):
        for attempt in ("RUN-ACME-SIM-ABCDEF1234567890", "ACME-SIM-xx", "ACME-SIM-../../glpi", "SIM-GLPI-ABCDEF1234"):
            with self.subTest(attempt=attempt):
                with patch.object(acme_sim_glpi.requests, "get") as get:
                    response = self.get(attempt)
                self.assertIn(response.status_code, (403, 404))
                get.assert_not_called()

    def test_stable_dependency_isolation_and_actor_acl_missing_fail_closed(self):
        # Stable does not ship portal.noc_runtime; no import-time dependency.
        self.assertNotIn("portal.noc_runtime", Path(acme_sim_glpi.__file__).read_text())
        for forged in (
            {},
            {"X-Tenant-ID": "ACME-TEST", "X-Actor-ID": "admin"},
            {"X-GLPI-Profile": "super-admin", "Cookie": "idp=forged"},
            {"X-Run-ID": GOOD["run_id"], "X-GLPI-READMY": "ALLOW"},
        ):
            with self.subTest(forged=forged):
                with patch.object(acme_sim_glpi, "_require_sim_actor_acl", return_value=False):
                    with patch.object(acme_sim_glpi.requests, "get") as upstream_get:
                        response = self.get(**forged)
                self.assert_unknown(response)
                self.assertEqual(response.json()["reason"], "SANDBOX_ACTOR_TENANT_ACL_NOT_QUALIFIED")
                upstream_get.assert_not_called()

    def test_disabled_or_unconfigured_core_is_unknown_no_network(self):
        for changed in ({"AIOPS_ACME_SANDBOX_ENABLED": "false"},
                        {"AIOPS_INTERNAL_TOKEN": ""},
                        {"CORE_URL": "https://attacker.example/path"},
                        {"CORE_URL": "http://user:password@aiops2-core:810"},
                        {"WORKER_URL": "https://attacker.example/receipt"}):
            with self.subTest(changed=changed):
                with patch.dict(os.environ, changed):
                    with patch.object(acme_sim_glpi.requests, "get") as get:
                        response = self.get()
                self.assert_unknown(response)
                get.assert_not_called()

    def test_core_200_resolved_synthetic_only_projects_exact_ids_and_unknown_transition_history(self):
        with patch.object(acme_sim_glpi.requests, "get", side_effect=good_reads()) as get:
            response = self.get(**{"X-Tenant-ID": "forged-other", "X-GLPI-Profile": "super-admin"})
        self.assertEqual(response.status_code, 200)
        self.assert_security(response)
        data = response.json()
        self.assertEqual(data["schema"], "aiops.portal.sim-glpi-readback.v1")
        self.assertEqual(data["state"], "RESOLVED")
        self.assertEqual(data["tenant_id"], "ACME-TEST")
        self.assertEqual(data["ticket"]["id"], GOOD["ticket_id"])
        self.assertEqual(data["ticket"]["current_state"], "RESOLVED")
        self.assertTrue(data["worker_no_effect_verified"])
        self.assertTrue(data["core_resolution_after_worker_verified"])
        self.assertEqual(data["worker_receipt_status"], "SIMULATED_NO_EFFECT")
        self.assertFalse(data["ticket"]["transition_history_attested"])
        self.assertEqual(data["readback_source"], "CORE_AND_WORKER_INDEPENDENT_SANDBOX_GET")
        self.assertEqual(data["provenance"], "SIMULATED")
        self.assertIsNone(data["observed_at"])
        self.assertFalse(data["human_allow"])
        self.assertFalse(data["native_glpi_readmy_attested"])
        self.assertFalse(data["host_e2e_qualified"])
        self.assertFalse(data["live_effects_allowed"])
        self.assertFalse(data["real_glpi_writes_allowed"])
        self.assertEqual(get.call_count, 3)
        self.assertEqual([c.args[0] for c in get.call_args_list],
                         [WORKER_URL, URL, WORKER_URL])
        for call in get.call_args_list:
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer " + INTERNAL)
            self.assertEqual(call.kwargs["timeout"], 3)
            self.assertIs(call.kwargs["allow_redirects"], False)

    def test_forged_200_is_never_human_allow_or_ticket_readback(self):
        mutations = [
            {"tenant_id": "ACME-PROD"}, {"attempt_id": "ACME-SIM-OTHER12345"},
            {"ticket_id": "12345"}, {"ticket_id": "SIM-GLPI-../../x"},
            {"ticket_status": "OPEN"}, {"run_status": "OPEN"},
            {"source": "GLPI_REAL"}, {"ticket_authority": "NATIVE_GLPI"},
            {"analysis_validated": False}, {"critic_validated": False},
            {"evidence_count": True}, {"evidence_count": 0},
            {"human_allow": True}, {"human_approved": True},
            {"real_glpi_writes_allowed": True}, {"live_effects_allowed": True},
            {"approval_issuer": "HUMAN_IDP"}, {"scenario_id": "OTHER"},
            {"mode": "LIVE"}, {"glpi_mode": "REAL"},
            {"incident_id": None}, {"run_id": None},
            {"worker_receipt_verified": False},
            {"resolution_after_worker_receipt": False},
            {"approval_fresh_at_resolution": False},
            {"approval_nonce_consumed": False},
            {"approval_nonce_revoked": True},
            {"approval_id": "SIM-APP-FORGED12345"},
            {"proposal_id": "SIM-PROP-FORGED12345"},
            {"source_hashes_qualified": False},
            {"source_event_ids": ["SYN-EVT-00000000"] * 7},
            {"request_sha256": "forged"},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                payload = {**GOOD, **mutation}
                with patch.object(acme_sim_glpi.requests, "get", side_effect=good_reads(core=payload)):
                    response = self.get()
                self.assert_unknown(response)

    def test_worker_receipt_forgery_replay_and_stale_approval_fail_closed(self):
        mutations = [
            {"tenant_id": "ACME-PROD"}, {"run_id": "RUN-OTHER-1234"},
            {"proposal_id": "SIM-PROP-OTHER1234"},
            {"approval_id": "SIM-APP-REPLAY1234"},
            {"approval_issuer": "HUMAN_IDP"},
            {"approval_kind": "HUMAN"},
            {"receipt_status": "SUCCESS"},
            {"receipt_phase": "POST_RESOLUTION"},
            {"core_status_at_validation": "RESOLVED"},
            {"resolution_verified": True},
            {"post_resolution_readback_required": False},
            {"effect_receipts": 1}, {"glpi_write": True},
            {"human_approved": True}, {"live_effects_allowed": True},
            {"audit_authority": "FORGED"},
            {"audit_transitions": ["WORKER_NO_EFFECT"]},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                worker = {**WORKER, **mutation}
                with patch.object(acme_sim_glpi.requests, "get",
                                  side_effect=good_reads(worker=worker)) as get:
                    self.assert_unknown(self.get())
                self.assertEqual(get.call_count, 3)
        # A changed Worker receipt across the final Core GET is a replay race.
        rotated = {**WORKER, "approval_id": "SIM-APP-ROTATED1234"}
        with patch.object(acme_sim_glpi.requests, "get",
                          side_effect=[upstream(WORKER), upstream(GOOD), upstream(rotated)]):
            self.assert_unknown(self.get())
        # A Core 200 from the old producer with no post-Worker fence is UNKNOWN.
        old_core = {k: v for k, v in GOOD.items()
                    if k not in ("worker_receipt_verified",
                                 "resolution_after_worker_receipt",
                                 "approval_fresh_at_resolution",
                                 "approval_nonce_consumed",
                                 "approval_nonce_revoked")}
        with patch.object(acme_sim_glpi.requests, "get",
                          side_effect=good_reads(core=old_core)):
            self.assert_unknown(self.get())

    def test_worker_unavailable_never_queries_core(self):
        with patch.object(acme_sim_glpi.requests, "get",
                          return_value=upstream(code=503)) as get:
            self.assert_unknown(self.get())
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.args[0], WORKER_URL)

    def test_transport_errors_redirects_and_unparseable_json_are_unknown(self):
        for status in (301, 302, 401, 403, 404, 500, 503):
            with self.subTest(status=status):
                with patch.object(acme_sim_glpi.requests, "get", return_value=upstream(code=status)):
                    self.assert_unknown(self.get())
        bad = upstream()
        bad.json.side_effect = ValueError("invalid")
        with patch.object(acme_sim_glpi.requests, "get", return_value=bad):
            self.assert_unknown(self.get())
        huge = upstream()
        huge.content = b"x" * 32769
        with patch.object(acme_sim_glpi.requests, "get", return_value=huge):
            self.assert_unknown(self.get())
        with patch.object(acme_sim_glpi.requests, "get", side_effect=acme_sim_glpi.requests.Timeout):
            self.assert_unknown(self.get())

    def test_no_mutation_route_and_no_native_glpi_business_endpoint(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self.client.request(method, "/api/demo/acme-sim-glpi/" + ATTEMPT).status_code, 405)
        paths = {route.path for route in main.app.routes}
        self.assertNotIn("/api/glpi/tickets/{ticket_id}", paths)
        self.assertNotIn("/api/glpi/tickets", paths)


if __name__ == "__main__":
    unittest.main()
