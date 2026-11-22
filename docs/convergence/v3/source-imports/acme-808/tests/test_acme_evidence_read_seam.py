import unittest
import hashlib
import json
from scripts.acme_worker_receipt_contract import CONSTANTS, FALSE_FLAGS, SCHEMA, TRANSITIONS, TRUE_FLAGS
from scripts.acme_evidence_read_seam import qualify_evidence_read
from scripts.acme_viewer_access_policy import ViewerDecision


class EvidenceReadSeamTests(unittest.TestCase):
    def test_denial_never_calls_upstream(self):
        for decision in (ViewerDecision(401, "VIEWER_UNAUTHENTICATED"),
                         ViewerDecision(403, "VIEWER_TENANT_DENIED"),
                         ViewerDecision(404, "ACME_RESOURCE_NOT_FOUND"),
                         ViewerDecision(503, "TENANT_ACL_NOT_QUALIFIED"),
                         None):
            calls = []
            def forbidden(_attempt):
                calls.append("LEAK")
                raise AssertionError("upstream called before ACL")
            result = qualify_evidence_read(decision, "ACME-SIM-" + "A" * 16,
                                           forbidden, forbidden)
            self.assertEqual(result["status"], "NO_GO")
            self.assertEqual(calls, [])

    def test_forged_positive_decision_reason_is_denied(self):
        calls = []
        def read(_attempt):
            calls.append(1)
            return {}
        result = qualify_evidence_read(ViewerDecision(200, "FORGED"),
                                       "ACME-SIM-" + "A" * 16, read, read)
        self.assertEqual(result["status"], "NO_GO")
        self.assertEqual(calls, [])

    def test_positive_policy_malformed_attempt_prevents_all_reads(self):
        calls = []
        def forbidden(_attempt):
            calls.append("upstream")
            return {}
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            "../../secrets", forbidden, forbidden)
        self.assertEqual(result["reason"], "ACME_ATTEMPT_INVALID")
        self.assertEqual(calls, [])

    def test_wrong_core_run_prevents_worker_read(self):
        calls = []
        def core(attempt):
            calls.append("core")
            return {"attempt_id": attempt, "tenant_id": "ACME-TEST",
                    "run_id": "RUN-SIM-" + "F" * 24}
        def worker(_attempt):
            calls.append("worker")
            return {}
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            "ACME-SIM-" + "A" * 16, core, worker)
        self.assertEqual(result["reason"], "CORE_BINDING_NOT_QUALIFIED")
        self.assertEqual(calls, ["core"])

    def test_wrong_core_attempt_prevents_worker_read(self):
        calls = []
        def core(_attempt):
            calls.append("core")
            return {"attempt_id": "OTHER"}
        def worker(_attempt):
            calls.append("worker")
            return {}
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            "ACME-SIM-" + "A" * 16, core, worker)
        self.assertEqual(result["reason"], "CORE_BINDING_NOT_QUALIFIED")
        self.assertEqual(calls, ["core"])

    def test_matching_offline_readbacks_never_disclose_tenant_data(self):
        attempt = "ACME-SIM-" + "A" * 16
        def ident(prefix, suffix="", length=24):
            return prefix + hashlib.sha256(
                ("ACME-TEST:" + attempt + suffix).encode("ascii")
            ).hexdigest()[:length].upper()
        ids = {"incident_id": ident("INC-SIM-"),
               "run_id": ident("RUN-SIM-"),
               "ticket_id": ident("SIM-GLPI-"),
               "proposal_id": ident("PROP-SIM-"),
               "approval_id": "SIM-APP-AAAA"}
        events = [ident("SYN-EVT-", ":" + str(i), 20) for i in range(1, 8)]
        digest = "a" * 64
        core = {"schema": "aiops.core-acme-sandbox-readback.v1",
                "attempt_id": attempt, "tenant_id": "ACME-TEST", **ids,
                "scenario_id": "ACME-SAN-PAYMENTS", "mode": "SIMULATION",
                "ticket_authority": "SIMULATED_ONLY",
                "glpi_mode": "SIMULATED_ONLY", "incident_status": "RESOLVED",
                "run_status": "RESOLVED", "ticket_status": "RESOLVED",
                "worker_receipt_verified": True,
                "terminal_ticket_receipt_verified": True,
                "resolution_after_worker_receipt": True,
                "approval_fresh_at_resolution": True,
                "human_approved": False, "live_effects_allowed": False,
                "real_glpi_writes_allowed": False, "execution_allowed": False,
                "effect_allowed": False, "worker_receipt_sha256": digest,
                "source_event_ids": events, "request_sha256": digest,
                "approval_nonce_consumed": True, "analysis_validated": True,
                "critic_validated": True, "source_hashes_qualified": True,
                "human_approval_claimed": False, "approval_nonce_revoked": False,
                "source_event_count": 7, "evidence_count": 2,
                "analysis_kind": "SYNTHETIC_FIXTURE",
                "approval_issuer": "TWIN_ACME_SIMULATED",
                "terminal_ticket_sha256": "b" * 64}
        worker = {"schema": SCHEMA, "attempt_id": attempt,
                  **CONSTANTS, **ids, "receipt_sha256": digest,
                  "core_request_sha256": digest, "core_source_event_ids": events,
                  "twin_approval_nonce_sha256": "b" * 64,
                  "effect_receipts": 0, "audit_transitions": list(TRANSITIONS)}
        worker.update({key: False for key in FALSE_FLAGS})
        worker.update({key: True for key in TRUE_FLAGS})
        worker["receipt_sha256"] = hashlib.sha256(json.dumps(
            {k: v for k, v in worker.items() if k != "receipt_sha256"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")).hexdigest()
        core["worker_receipt_sha256"] = worker["receipt_sha256"]
        calls = []
        def read_core(value):
            calls.append(("core", value))
            return core
        def read_worker(value):
            calls.append(("worker", value))
            return worker
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            attempt, read_core, read_worker)
        self.assertEqual(result, {
            "status": "OFFLINE_CONSISTENT_ONLY",
            "reason": "NO_RUNTIME_ATTESTATION"})
        self.assertEqual(calls, [("core", attempt), ("worker", attempt)])
        self.assertNotIn(ids["run_id"], repr(result))

    def test_worker_mismatch_after_canonical_core_preflight_is_redacted(self):
        attempt = "ACME-SIM-" + "A" * 16
        run = "RUN-SIM-" + hashlib.sha256(
            ("ACME-TEST:" + attempt).encode("ascii")
        ).hexdigest()[:24].upper()
        calls = []
        def core(value):
            calls.append("core")
            return {"attempt_id": value, "tenant_id": "ACME-TEST",
                    "run_id": run, "secret": "CORE_PRIVATE"}
        def worker(value):
            calls.append("worker")
            return {"attempt_id": value, "secret": "WORKER_PRIVATE"}
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            attempt, core, worker)
        self.assertEqual(calls, ["core", "worker"])
        self.assertEqual(result["reason"], "CORE_WORKER_BINDING_NOT_QUALIFIED")
        self.assertNotIn("PRIVATE", repr(result))

    def test_worker_mismatch_does_not_leak_worker_payload(self):
        attempt = "ACME-SIM-" + "A" * 16
        calls = []
        def core(value):
            calls.append("core")
            return {"attempt_id": value, "secret": "CORE_PRIVATE"}
        def worker(value):
            calls.append("worker")
            return {"attempt_id": value, "secret": "WORKER_PRIVATE"}
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            attempt, core, worker)
        self.assertEqual(calls, ["core"])
        self.assertEqual(result["reason"], "CORE_BINDING_NOT_QUALIFIED")
        self.assertNotIn("PRIVATE", repr(result))

    def test_no_data_disclosed_on_upstream_failure(self):
        def broken(_attempt):
            raise RuntimeError("secret bearer must not leak")
        result = qualify_evidence_read(
            ViewerDecision(200, "POLICY_CONDITIONS_SATISFIED_ONLY"),
            "ACME-SIM-" + "A" * 16, broken, broken)
        self.assertNotIn("secret", repr(result))
        self.assertEqual(result["reason"], "EVIDENCE_READBACK_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
