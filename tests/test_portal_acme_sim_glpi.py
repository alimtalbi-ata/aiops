"""Portal ACME SIM-GLPI: independent Core sandbox GET, no human READ/READMY."""
import hashlib
import json
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
    "critic_validated": True, "analysis_kind": "SYNTHETIC_FIXTURE", "evidence_count": 2,
    "approval_issuer": "TWIN_ACME_SIMULATED",
    "human_approved": False, "live_effects_allowed": False,
    "real_glpi_writes_allowed": False,
    "human_approval_claimed": False, "execution_allowed": False,
    "effect_allowed": False, "glpi_mode": "SIMULATED_ONLY",
    "schema": "aiops.core-acme-sandbox-readback.v1",
    "proposal_id": "SIM-PROP-1234567890",
    "approval_id": "SIM-APP-1234567890",
    "source_event_count": 7, "source_hashes_qualified": True,
    "source_event_ids": ["SYN-EVT-" + hashlib.sha256(
        ("ACME-TEST:" + ATTEMPT + ":" + str(i)).encode("ascii")
    ).hexdigest()[:20].upper() for i in range(1, 8)],
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
    "proposal_id": GOOD["proposal_id"], "ticket_id": GOOD["ticket_id"],
    "approval_id": GOOD["approval_id"],
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


# Controlled positive-shape fixtures: these are NOT Core/Worker authority.
WORKER["core_request_sha256"] = GOOD["request_sha256"]
WORKER["core_source_event_ids"] = list(GOOD["source_event_ids"])
WORKER["twin_approval_nonce_sha256"] = "b" * 64
WORKER["receipt_sha256"] = hashlib.sha256(json.dumps(
    WORKER, sort_keys=True, separators=(",", ":"), ensure_ascii=True
).encode("ascii")).hexdigest()
GOOD["worker_receipt_sha256"] = WORKER["receipt_sha256"]
GOOD["terminal_ticket_receipt_verified"] = True
GOOD["terminal_ticket_sha256"] = hashlib.sha256(json.dumps({
    "schema": "aiops.portal.sim-glpi-ticket-digest.v1",
    "tenant_id": "ACME-TEST", "attempt_id": ATTEMPT,
    "incident_id": GOOD["incident_id"], "run_id": GOOD["run_id"],
    "ticket_id": GOOD["ticket_id"], "ticket_status": "RESOLVED",
    "core_request_sha256": GOOD["request_sha256"],
    "worker_receipt_sha256": WORKER["receipt_sha256"],
}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def upstream(value=None, code=200):
    response = Mock()
    response.status_code = code
    response.content = b'{"synthetic":true}'
    response.json.return_value = dict(GOOD if value is None else value)
    return response


def good_reads(core=None, worker=None):
    receipt = WORKER if worker is None else worker
    final = GOOD if core is None else core
    return [upstream(receipt), upstream(final), upstream(receipt), upstream(final)]


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
        self.assertEqual(data["authority"], "SIMULATED_ONLY")
        self.assertEqual(data["ticket_authority"], "SIMULATED_ONLY")
        self.assertFalse(data["human_allow"])
        self.assertEqual(data["authority"], "SIMULATED_ONLY")
        self.assertFalse(data["real_glpi_writes_allowed"])
        self.assertNotIn("ticket", data)
        self.assertNotIn("run_id", data)
        self.assert_security(response)

    def test_public_shell_has_simulated_badge_no_ids_and_inert_human_actions(self):
        with patch.object(acme_sim_glpi, "_direct_get", side_effect=AssertionError("Core GET")):
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

    def test_no_viewer_no_core_business_get(self):
        for headers in ({}, {"Authorization": "Bearer bad"}, {"Authorization": "Basic " + TOKEN}):
            with self.subTest(headers=headers):
                with patch.object(acme_sim_glpi, "_direct_get") as get:
                    response = self.client.get("/api/demo/acme-sim-glpi/" + ATTEMPT, headers=headers)
                self.assert_unknown(response, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                get.assert_not_called()

    def test_unconfigured_viewer_is_503_before_core(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            with patch.object(acme_sim_glpi, "_direct_get") as get:
                response = self.get()
        self.assert_unknown(response)
        get.assert_not_called()

    def test_wrong_namespace_denied_without_upstream_even_if_viewer_valid(self):
        for attempt in ("RUN-ACME-SIM-ABCDEF1234567890", "ACME-SIM-xx", "ACME-SIM-../../glpi", "SIM-GLPI-ABCDEF1234"):
            with self.subTest(attempt=attempt):
                with patch.object(acme_sim_glpi, "_direct_get") as get:
                    response = self.get(attempt)
                self.assertIn(response.status_code, (403, 404))
                get.assert_not_called()

    def test_viewer_token_cannot_alias_internal_or_admin_credential(self):
        for privileged in ("AIOPS_INTERNAL_TOKEN", "AIOPS_ADMIN_TOKEN"):
            with self.subTest(privileged=privileged):
                with patch.dict(os.environ, {privileged: TOKEN}):
                    with patch.object(acme_sim_glpi, "_direct_get") as upstream_get:
                        response = self.get()
                self.assert_unknown(response)
                self.assertEqual(response.json()["reason"], "portal_viewer_privileged_token_reuse_denied")
                upstream_get.assert_not_called()
        self.assertNotIn("AIOPS_INTERNAL_TOKEN", acme_sim_glpi.PAGE)
        self.assertNotIn("AIOPS_ADMIN_TOKEN", acme_sim_glpi.PAGE)
        script = Path(acme_sim_glpi.__file__).with_name("acme_sim_glpi_client.js").read_text()
        self.assertNotIn("AIOPS_INTERNAL_TOKEN", script)
        self.assertNotIn("AIOPS_ADMIN_TOKEN", script)

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
                    with patch.object(acme_sim_glpi, "_direct_get") as upstream_get:
                        response = self.get(**forged)
                self.assert_unknown(response)
                self.assertEqual(response.json()["reason"], "SANDBOX_ACTOR_TENANT_ACL_NOT_QUALIFIED")
                upstream_get.assert_not_called()

    def test_stable_actual_acl_guard_is_not_mock_allow(self):
        # Unpatch the positive-shape fixture: real stable guard must deny.
        self.actor_acl_fixture.stop()
        try:
            with patch.dict(os.environ, {"AIOPS_ACME_SANDBOX_ENABLED": "true",
                                       "AIOPS_SIM_GLPI_ACTOR_ID": "admin",
                                       "AIOPS_SIM_GLPI_TENANT": "ACME-TEST"}):
                with patch.object(acme_sim_glpi, "_direct_get") as upstream_get:
                    response = self.get(**{"X-Tenant-ID": "ACME-TEST",
                                           "X-Actor-ID": "admin",
                                           "X-GLPI-READMY": "ALLOW"})
            self.assert_unknown(response)
            self.assertEqual(response.json()["reason"], "SANDBOX_ACTOR_TENANT_ACL_NOT_QUALIFIED")
            upstream_get.assert_not_called()
        finally:
            self.actor_acl_fixture.start()

    def test_disabled_or_unconfigured_core_is_unknown_no_network(self):
        for changed in ({"AIOPS_ACME_SANDBOX_ENABLED": "false"},
                        {"AIOPS_INTERNAL_TOKEN": ""},
                        {"CORE_URL": "https://attacker.example/path"},
                        {"CORE_URL": "http://user:password@aiops2-core:810"},
                        {"CORE_URL": "http://aiops2-core:811"},
                        {"WORKER_URL": "http://aiops2-worker:810"},
                        {"WORKER_URL": "https://attacker.example/receipt"},
                        {"CORE_URL": "http://[::1:810"},
                        {"WORKER_URL": "http://aiops2-worker:notaport"},
                        {"CORE_URL": "http://aiops2-core:810#fragment"}):
            with self.subTest(changed=changed):
                with patch.dict(os.environ, changed):
                    with patch.object(acme_sim_glpi, "_direct_get") as get:
                        response = self.get()
                self.assert_unknown(response)
                get.assert_not_called()

    def test_core_200_resolved_synthetic_only_projects_exact_ids_and_unknown_transition_history(self):
        with patch.object(acme_sim_glpi, "_direct_get", side_effect=good_reads()) as get:
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
        self.assertTrue(data["terminal_ticket_digest_verified"])
        self.assertEqual(data["independent_final_read_rounds"], 2)
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
        self.assertEqual(get.call_count, 4)
        self.assertEqual([c.args[0] for c in get.call_args_list],
                         [WORKER_URL, URL, WORKER_URL, URL])
        for call in get.call_args_list:
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer " + INTERNAL)
            self.assertEqual(call.kwargs["timeout"], 3)
            self.assertIs(call.kwargs["allow_redirects"], False)
            self.assertEqual(call.kwargs["proxies"],
                             {"http": "", "https": "", "all": ""})

    def test_independent_rounds_reject_bool_int_equivalence_forgery(self):
        # Python considers True == 1 and False == 0 in nested dicts.  The
        # first round must be JSON-type-identical to the second, not merely
        # Python-equal, before any SIM-GLPI RESOLVED projection is allowed.
        for core_change, worker_change in (
            ({"worker_receipt_verified": 1}, {}),
            ({}, {"human_approved": 0}),
        ):
            with self.subTest(core_change=core_change, worker_change=worker_change):
                first_core = {**GOOD, **core_change}
                first_worker = {**WORKER, **worker_change}
                self.assertEqual(first_core, GOOD)
                self.assertEqual(first_worker, WORKER)
                reads = [upstream(first_worker), upstream(first_core),
                         upstream(WORKER), upstream(GOOD)]
                with patch.object(acme_sim_glpi, "_direct_get",
                                  side_effect=reads) as get:
                    response = self.get()
                self.assert_unknown(response)
                self.assertEqual(response.json()["reason"],
                                 "CORE_SIMULATED_TICKET_NOT_ATTESTED")
                self.assertEqual(get.call_count, 4)

    def test_overdeep_sandbox_json_is_503_not_uncaught_500(self):
        # Even a forged 200 from an upstream must never turn a malformed
        # deeply nested receipt into a Portal 500 or a RESOLVED projection.
        invalid = upstream(WORKER)
        invalid.json.side_effect = RecursionError("overdeep JSON decoder")
        with patch.object(acme_sim_glpi, "_direct_get", return_value=invalid) as get:
            response = self.get()
        self.assert_unknown(response)
        self.assertEqual(response.json()["reason"],
                         "CORE_SIMULATED_TICKET_NOT_ATTESTED")
        self.assertEqual(get.call_count, 1)

        # Defensive second boundary: a JSON-shaped object accepted by the
        # decoder may still exceed the canonical serializer's recursion limit.
        nested = {}
        for _ in range(1100):
            nested = {"nested": nested}
        forged_core = {**GOOD, "untrusted_nested": nested}
        with patch.object(acme_sim_glpi, "_direct_get",
                          side_effect=good_reads(core=forged_core)) as get:
            response = self.get()
        self.assert_unknown(response)
        self.assertEqual(response.json()["reason"],
                         "CORE_SIMULATED_TICKET_NOT_ATTESTED")
        self.assertEqual(get.call_count, 4)

    def test_poisoned_proxy_environment_never_receives_internal_bearer(self):
        # Controlled fixture only: actor+tenant verifier is still absent on host.
        # An environment proxy must not intercept the fixed Core/Worker GETs.
        with patch.dict(os.environ, {
            "HTTP_PROXY": "http://untrusted.example:8080",
            "HTTPS_PROXY": "http://untrusted.example:8080",
            "ALL_PROXY": "http://untrusted.example:8080",
        }):
            with patch.object(acme_sim_glpi, "_direct_get",
                              side_effect=good_reads()) as get:
                response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_count, 4)
        for call in get.call_args_list:
            self.assertEqual(call.kwargs["proxies"],
                             {"http": "", "https": "", "all": ""})
            self.assertEqual(call.kwargs["headers"]["Authorization"],
                             "Bearer " + INTERNAL)

    def test_direct_session_rejects_ambient_netrc_and_proxy_credential_override(self):
        # Regression: requests.get(..., proxies={...empty...}) still honors
        # ~/.netrc. A malicious host entry can replace the internal bearer.
        # Intercept the prepared request before any network operation.
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            netrc = Path(folder) / "hostile.netrc"
            netrc.write_text("machine aiops2-worker login attacker password forged\n")
            netrc.chmod(0o600)
            with patch.dict(os.environ, {
                "NETRC": str(netrc),
                "HTTP_PROXY": "http://untrusted.example:8080",
                "HTTPS_PROXY": "http://untrusted.example:8080",
                "ALL_PROXY": "http://untrusted.example:8080",
            }):
                with patch.object(acme_sim_glpi.requests.sessions.Session, "send",
                                  return_value=upstream(WORKER)) as send:
                    result = acme_sim_glpi._direct_get(
                        WORKER_URL,
                        headers={"Authorization": "Bearer " + INTERNAL,
                                 "Accept": "application/json"},
                        timeout=3, allow_redirects=False,
                        proxies={"http": "", "https": "", "all": ""})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(send.call_count, 1)
        prepared = send.call_args.args[0]
        self.assertEqual(prepared.url, WORKER_URL)
        self.assertEqual(prepared.headers["Authorization"], "Bearer " + INTERNAL)
        self.assertNotIn("Basic ", prepared.headers["Authorization"])
        self.assertNotIn("untrusted.example", str(send.call_args.kwargs))
        self.assertFalse(send.call_args.kwargs["allow_redirects"])

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
                with patch.object(acme_sim_glpi, "_direct_get", side_effect=good_reads(core=payload)):
                    response = self.get()
                self.assert_unknown(response)

    def test_core_terminal_rejects_rehashed_or_extra_human_authority_claims(self):
        # The real Core 018 producer has a closed readback schema. A valid
        # terminal digest does not authorize any new IdP/GLPI/ACL claims.
        for injected in (
            {"human_allow": True},
            {"native_glpi_readmy_attested": True},
            {"idp_issuer": "forged-idp"},
            {"actor_acl_verified": True},
            {"tenant_acl_verified": True},
            {"glpi_write": False},
            {"ticket_user_readmy": "ALLOW"},
            {"live_executor": "AUTHORIZED"},
            {"analysis_kind": "HUMAN_VERIFIED"},
        ):
            with self.subTest(injected=injected):
                core = {**GOOD, **injected}
                with self.assertRaisesRegex(
                        ValueError, "core_(terminal_schema|analysis_kind)_unqualified"):
                    acme_sim_glpi._project(core, WORKER, ATTEMPT)
                with patch.object(acme_sim_glpi, "_direct_get",
                                  side_effect=good_reads(core=core)) as get:
                    self.assert_unknown(self.get())
                self.assertEqual(get.call_count, 4)

    def test_rg19_worker_ticket_binding_rejects_missing_or_foreign_rehashed_ticket(self):
        # Stable Worker RG-ACME-19 includes ticket_id in the no-effect receipt.
        # A legacy receipt without it or a forged foreign ticket is not a
        # qualified terminal readback, even with both SHA256s recomputed.
        self.assertEqual(WORKER["ticket_id"], GOOD["ticket_id"])
        for foreign in (None, "SIM-GLPI-FOREIGN123456", 42):
            with self.subTest(foreign=foreign):
                worker = dict(WORKER)
                if foreign is None:
                    worker.pop("ticket_id")
                else:
                    worker["ticket_id"] = foreign
                worker["receipt_sha256"] = hashlib.sha256(json.dumps(
                    {k: v for k, v in worker.items() if k != "receipt_sha256"},
                    sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("ascii")).hexdigest()
                core = {**GOOD, "worker_receipt_sha256": worker["receipt_sha256"]}
                core["terminal_ticket_sha256"] = hashlib.sha256(json.dumps({
                    "schema": "aiops.portal.sim-glpi-ticket-digest.v1",
                    "tenant_id": core["tenant_id"], "attempt_id": ATTEMPT,
                    "incident_id": core["incident_id"], "run_id": core["run_id"],
                    "ticket_id": core["ticket_id"], "ticket_status": "RESOLVED",
                    "core_request_sha256": core["request_sha256"],
                    "worker_receipt_sha256": worker["receipt_sha256"],
                }, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("ascii")).hexdigest()
                with patch.object(acme_sim_glpi, "_direct_get",
                                  side_effect=good_reads(core=core, worker=worker)) as get:
                    response = self.get()
                self.assert_unknown(response)
                self.assertEqual(response.json()["reason"],
                                 "CORE_SIMULATED_TICKET_NOT_ATTESTED")
                self.assertEqual(get.call_count, 4)

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
                with patch.object(acme_sim_glpi, "_direct_get",
                                  side_effect=good_reads(worker=worker)) as get:
                    self.assert_unknown(self.get())
                self.assertEqual(get.call_count, 4)
        # A changed Worker receipt across the final Core GET is a replay race.
        rotated = {**WORKER, "approval_id": "SIM-APP-ROTATED1234"}
        with patch.object(acme_sim_glpi, "_direct_get",
                          side_effect=[upstream(WORKER), upstream(GOOD), upstream(rotated), upstream(GOOD)]):
            self.assert_unknown(self.get())
        # Core final read must also remain byte-for-byte consistent.
        rotated_core = {**GOOD, "terminal_ticket_sha256": "f" * 64}
        with patch.object(acme_sim_glpi, "_direct_get",
                          side_effect=[upstream(WORKER), upstream(GOOD),
                                       upstream(WORKER), upstream(rotated_core)]) as get:
            self.assert_unknown(self.get())
        self.assertEqual(get.call_count, 4)
        # A Core 200 from the old producer with no post-Worker fence is UNKNOWN.
        old_core = {k: v for k, v in GOOD.items()
                    if k not in ("worker_receipt_verified",
                                 "resolution_after_worker_receipt",
                                 "approval_fresh_at_resolution",
                                 "approval_nonce_consumed",
                                 "approval_nonce_revoked")}
        with patch.object(acme_sim_glpi, "_direct_get",
                          side_effect=good_reads(core=old_core)):
            self.assert_unknown(self.get())

    def test_digest_and_durable_terminal_receipt_are_required(self):
        for mutation in (
            {"terminal_ticket_receipt_verified": False},
            {"terminal_ticket_sha256": "0" * 64},
            {"worker_receipt_sha256": "0" * 64},
            {"source_event_ids": list(reversed(GOOD["source_event_ids"]))},
        ):
            with self.subTest(core=mutation):
                with patch.object(acme_sim_glpi, "_direct_get",
                                  side_effect=good_reads(core={**GOOD, **mutation})):
                    self.assert_unknown(self.get())
        for missing in ("terminal_ticket_sha256", "worker_receipt_sha256",
                        "terminal_ticket_receipt_verified"):
            old = {k: v for k, v in GOOD.items() if k != missing}
            with self.subTest(missing=missing):
                with patch.object(acme_sim_glpi, "_direct_get",
                                  side_effect=good_reads(core=old)):
                    self.assert_unknown(self.get())
        for mutation in (
            {"receipt_sha256": "0" * 64},
            {"core_request_sha256": "0" * 64},
            {"core_source_event_ids": list(reversed(GOOD["source_event_ids"]))},
            {"twin_approval_nonce_sha256": "invalid"},
        ):
            with self.subTest(worker=mutation):
                with patch.object(acme_sim_glpi, "_direct_get",
                                  side_effect=good_reads(worker={**WORKER, **mutation})):
                    self.assert_unknown(self.get())

    def test_rehashed_worker_extra_authority_claims_fail_even_with_matching_core_digests(self):
        # A checksum is not an authority signature. Recompute both digests to
        # prove the Portal rejects *schema injection*, not only broken hashes.
        for injected in (
            {"human_allow": True},
            {"native_glpi_readmy_attested": True},
            {"ticket_authority": "REAL_GLPI"},
            {"live_executor": "AUTHORIZED"},
        ):
            with self.subTest(injected=injected):
                worker = {**WORKER, **injected}
                worker["receipt_sha256"] = hashlib.sha256(json.dumps(
                    {k: v for k, v in worker.items() if k != "receipt_sha256"},
                    sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("ascii")).hexdigest()
                core = {**GOOD, "worker_receipt_sha256": worker["receipt_sha256"]}
                core["terminal_ticket_sha256"] = hashlib.sha256(json.dumps({
                    "schema": "aiops.portal.sim-glpi-ticket-digest.v1",
                    "tenant_id": "ACME-TEST", "attempt_id": ATTEMPT,
                    "incident_id": core["incident_id"], "run_id": core["run_id"],
                    "ticket_id": core["ticket_id"], "ticket_status": "RESOLVED",
                    "core_request_sha256": core["request_sha256"],
                    "worker_receipt_sha256": worker["receipt_sha256"],
                }, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("ascii")).hexdigest()
                with self.assertRaisesRegex(ValueError, "worker_receipt_schema_unqualified"):
                    acme_sim_glpi._project(core, worker, ATTEMPT)
                with patch.object(acme_sim_glpi, "_direct_get",
                                  side_effect=good_reads(core=core, worker=worker)) as get:
                    self.assert_unknown(self.get())
                self.assertEqual(get.call_count, 4)

    def test_worker_unavailable_never_queries_core(self):
        with patch.object(acme_sim_glpi, "_direct_get",
                          return_value=upstream(code=503)) as get:
            self.assert_unknown(self.get())
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.args[0], WORKER_URL)

    def test_transport_errors_redirects_and_unparseable_json_are_unknown(self):
        for status in (301, 302, 401, 403, 404, 500, 503):
            with self.subTest(status=status):
                with patch.object(acme_sim_glpi, "_direct_get", return_value=upstream(code=status)):
                    self.assert_unknown(self.get())
        bad = upstream()
        bad.json.side_effect = ValueError("invalid")
        with patch.object(acme_sim_glpi, "_direct_get", return_value=bad):
            self.assert_unknown(self.get())
        huge = upstream()
        huge.content = b"x" * 32769
        with patch.object(acme_sim_glpi, "_direct_get", return_value=huge):
            self.assert_unknown(self.get())
        with patch.object(acme_sim_glpi, "_direct_get", side_effect=acme_sim_glpi.requests.Timeout):
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
