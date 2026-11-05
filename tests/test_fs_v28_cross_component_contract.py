"""Read-only cross-component filesystem DEMO contract, no Temporal dispatch."""
import unittest
from app.core.fs_v28_read_model import project
from app.core.fs_v28_transition_guard import validate

INC = "INC-DEMO-FS-001"
RUN = "RUN-4FABD1786F107E51"
EVD = "EVD-D2069BA816126499"

def run(status):
    return {"run_id": RUN, "incident_id": INC, "scenario_id": "FS-DEBIAN-SYNTHETIC", "mode": "DEMO", "status": status}

def evidence():
    return {"evidence_id": EVD, "incident_id": INC, "run_id": RUN}

def event(stage, n, **extra):
    return {"event_id": "v28-" + str(n), "incident_id": INC, "run_id": RUN, "evidence_id": EVD,
            "mode": "DEMO", "live_effects": False, "stage": stage, **extra}

def guard(events):
    return validate(events, incident_id=INC, run_id=RUN, evidence_id=EVD)

class FilesystemDemoContractTests(unittest.TestCase):
    def test_created_and_evidence_get_are_inert(self):
        view = project(run("CREATED"), evidence())
        self.assertEqual(view["status"], "CREATED")
        self.assertFalse(view["can_start"])
        self.assertFalse(view["can_resolve"])
        self.assertEqual(guard([])["status"], "CREATED")

    def test_observe_analyst_critic_are_non_terminal(self):
        events = [event("OBSERVE", 1), event("ANALYST", 2), event("CRITIC", 3)]
        for n, stage in enumerate(("OBSERVE", "ANALYST", "CRITIC"), 1):
            self.assertEqual(guard(events[:n])["status"], "IN_PROGRESS")
            view = project(run(stage), evidence())
            self.assertEqual(view["status"], "IN_PROGRESS")
            self.assertFalse(view["can_resolve"])

    def test_policy_denial_terminal_without_resolution(self):
        events = [event("OBSERVE", 1), event("ANALYST", 2), event("CRITIC", 3),
                  event("POLICY", 4, decision="DENY")]
        self.assertEqual(guard(events)["status"], "BLOCKED_NO_EFFECT")
        view = project(run("BLOCKED_NO_EFFECT"), evidence(),
                       {"state": "DENY", "run_id": RUN, "incident_id": INC, "live_effects": False})
        self.assertEqual(view["status"], "BLOCKED_NO_EFFECT")
        self.assertFalse(view["can_resolve"])
        self.assertFalse(view["can_start"])
        self.assertFalse(view["live_effects"])
        self.assertEqual(guard(events + [dict(events[-1])])["status"], "BLOCKED_NO_EFFECT")
        self.assertEqual(guard(events + [event("RESOLVE", 5)])["status"], "UNAVAILABLE")
        self.assertEqual(project(run("RESOLVED"), evidence())["status"], "UNAVAILABLE")

    def test_denial_without_attestation_is_not_terminal_proof(self):
        for policy in (None, {"state": "DENY", "run_id": RUN, "incident_id": INC},
                       {"state": "DENY", "run_id": "OTHER", "incident_id": INC, "live_effects": False}):
            with self.subTest(policy=policy):
                self.assertEqual(project(run("BLOCKED"), evidence(), policy)["status"], "UNAVAILABLE")

    def test_correlation_mismatch_is_fail_closed(self):
        self.assertEqual(project(run("CREATED"), {**evidence(), "run_id": "OTHER"})["status"], "UNAVAILABLE")
        self.assertEqual(guard([event("OBSERVE", 1, evidence_id="OTHER")])["status"], "UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()
