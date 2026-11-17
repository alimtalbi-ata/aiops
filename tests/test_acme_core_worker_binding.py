"""Negative-first offline binding checks; no network, DB, or Temporal."""
import unittest
import hashlib
import json
from scripts.acme_core_worker_binding import inspect_core_worker_binding
from scripts.acme_worker_receipt_contract import CONSTANTS, FALSE_FLAGS, SCHEMA, TRANSITIONS, TRUE_FLAGS


def sample():
    result = {"schema": SCHEMA, "attempt_id": "ACME-SIM-" + "A" * 16,
              **CONSTANTS, "effect_receipts": 0,
              "audit_transitions": list(TRANSITIONS)}
    result.update({key: False for key in FALSE_FLAGS})
    result.update({key: True for key in TRUE_FLAGS})
    result['core_request_sha256'] = 'a' * 64
    result['twin_approval_nonce_sha256'] = 'b' * 64
    result['core_source_event_ids'] = [
        'SYN-EVT-' + hashlib.sha256(('ACME-TEST:' + result['attempt_id'] + ':' + str(i)).encode('ascii')).hexdigest()[:20].upper() for i in range(1, 8)]
    result['receipt_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')).hexdigest()
    return result

ATTEMPT = "ACME-SIM-" + "A" * 16
def canonical(prefix, suffix="", length=24):
    return prefix + hashlib.sha256(
        ("ACME-TEST:" + ATTEMPT + suffix).encode("ascii")
    ).hexdigest()[:length].upper()


RUN = canonical("RUN-SIM-")
INC = canonical("INC-SIM-")
TICKET = canonical("SIM-GLPI-")
PROPOSAL = canonical("PROP-SIM-")
APPROVAL = "SIM-APP-AAAA"
HASH = "a" * 64
EVENTS = [canonical("SYN-EVT-", ":" + str(i), 20) for i in range(1, 8)]


def pair():
    worker = sample()
    worker.update({"incident_id": INC, "run_id": RUN, "ticket_id": TICKET,
                   "proposal_id": PROPOSAL, "approval_id": APPROVAL,
                   "core_request_sha256": HASH,
                   "core_source_event_ids": EVENTS})
    worker["receipt_sha256"] = hashlib.sha256(json.dumps(
        {k: v for k, v in worker.items() if k != "receipt_sha256"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")).hexdigest()
    core = {"schema": "aiops.core-acme-sandbox-readback.v1",
            "attempt_id": ATTEMPT, "tenant_id": "ACME-TEST",
            "scenario_id": "ACME-SAN-PAYMENTS", "mode": "SIMULATION",
            "incident_id": INC, "run_id": RUN, "ticket_id": TICKET,
            "proposal_id": PROPOSAL, "approval_id": APPROVAL,
            "ticket_authority": "SIMULATED_ONLY", "glpi_mode": "SIMULATED_ONLY",
            "incident_status": "RESOLVED", "run_status": "RESOLVED",
            "ticket_status": "RESOLVED", "worker_receipt_verified": True,
            "terminal_ticket_receipt_verified": True,
            "resolution_after_worker_receipt": True,
            "approval_fresh_at_resolution": True,
            "human_approved": False, "live_effects_allowed": False,
            "real_glpi_writes_allowed": False, "execution_allowed": False,
            "effect_allowed": False, "worker_receipt_sha256": worker["receipt_sha256"],
            "source_event_ids": EVENTS, "request_sha256": HASH,
            "approval_nonce_consumed": True, "analysis_validated": True,
            "critic_validated": True, "source_hashes_qualified": True,
            "human_approval_claimed": False, "approval_nonce_revoked": False,
            "source_event_count": 7, "evidence_count": 2,
            "analysis_kind": "SYNTHETIC_FIXTURE",
            "approval_issuer": "TWIN_ACME_SIMULATED",
            "terminal_ticket_sha256": "b" * 64}
    return core, worker


class CoreWorkerBindingTests(unittest.TestCase):
    def test_matching_declarations_only(self):
        self.assertEqual(inspect_core_worker_binding(*pair()), [])

    def test_mismatched_run_and_tenant(self):
        core, worker = pair()
        worker["run_id"] = "RUN-SIM-OTHER"
        worker["tenant_id"] = "OTHER"
        errors = inspect_core_worker_binding(core, worker)
        self.assertIn("JOIN_RUN_ID_MISMATCH", errors)
        self.assertIn("JOIN_TENANT_ID_MISMATCH", errors)

    def test_digest_and_event_chain(self):
        core, worker = pair()
        worker["receipt_sha256"] = "b" * 64
        worker["core_source_event_ids"] = EVENTS[:-1]
        self.assertIn("JOIN_WORKER_RECEIPT_DIGEST_MISMATCH",
                      inspect_core_worker_binding(core, worker))
        self.assertIn("JOIN_SOURCE_EVENTS_MISMATCH",
                      inspect_core_worker_binding(core, worker))

    def test_jointly_forged_matching_run_is_rejected(self):
        core, worker = pair()
        core["run_id"] = worker["run_id"] = "RUN-SIM-FORGED"
        self.assertIn("CORE_RUN_ID_NONCANONICAL",
                      inspect_core_worker_binding(core, worker))

    def test_jointly_forged_matching_source_ids_rejected(self):
        core, worker = pair()
        core["source_event_ids"] = worker["core_source_event_ids"] = [
            "SYN-EVT-FORGED" + str(i) for i in range(7)]
        self.assertIn("CORE_SOURCE_EVENTS_NONCANONICAL",
                      inspect_core_worker_binding(core, worker))

    def test_resolved_missing_nonce_consumption_rejected(self):
        core, worker = pair()
        core["approval_nonce_consumed"] = False
        self.assertIn("CORE_APPROVAL_NONCE_CONSUMED_NOT_VERIFIED",
                      inspect_core_worker_binding(core, worker))

    def test_resolved_evidence_count_and_terminal_digest_rejected(self):
        core, worker = pair()
        core["source_event_count"] = True
        core["terminal_ticket_sha256"] = "INVALID"
        errors = inspect_core_worker_binding(core, worker)
        self.assertIn("CORE_SOURCE_EVENT_COUNT_INVALID", errors)
        self.assertIn("CORE_TERMINAL_TICKET_DIGEST_INVALID", errors)

    def test_prepared_not_resolved(self):
        core, worker = pair()
        core["ticket_status"] = "PREPARED"
        core["worker_receipt_verified"] = False
        self.assertIn("CORE_TICKET_STATUS_INVALID",
                      inspect_core_worker_binding(core, worker))
        self.assertIn("CORE_WORKER_RECEIPT_VERIFIED_NOT_VERIFIED",
                      inspect_core_worker_binding(core, worker))

    def test_live_effects_and_missing(self):
        core, worker = pair()
        core["effect_allowed"] = 0
        self.assertIn("CORE_EFFECT_ALLOWED_UNSAFE",
                      inspect_core_worker_binding(core, worker))
        self.assertIn("CORE_READBACK_INVALID",
                      inspect_core_worker_binding(None, worker))


if __name__ == "__main__":
    unittest.main()
