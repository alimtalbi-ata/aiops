"""Negative-first offline binding checks; no network, DB, or Temporal."""
import unittest
from scripts.acme_core_worker_binding import inspect_core_worker_binding
from tests.test_acme_worker_receipt_contract import sample

ATTEMPT = "ACME-SIM-" + "A" * 16
RUN = "RUN-SIM-AAAA"
INC = "INC-SIM-AAAA"
TICKET = "SIM-GLPI-AAAA"
PROPOSAL = "PROP-SIM-AAAA"
APPROVAL = "SIM-APP-AAAA"
HASH = "a" * 64
EVENTS = ["SYN-EVT-" + str(i) for i in range(7)]


def pair():
    worker = sample()
    worker.update({"incident_id": INC, "run_id": RUN, "ticket_id": TICKET,
                   "proposal_id": PROPOSAL, "approval_id": APPROVAL,
                   "receipt_sha256": HASH, "core_request_sha256": HASH,
                   "core_source_event_ids": EVENTS})
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
            "effect_allowed": False, "worker_receipt_sha256": HASH,
            "source_event_ids": EVENTS, "request_sha256": HASH}
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
