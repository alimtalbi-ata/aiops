"""Synthetic-only HTTP/Policy unit contract: no real HITL, Temporal or LIVE."""
import copy
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-hitl-test-only"}):
    from portal import main
from fastapi.testclient import TestClient
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_hitl_story import STATES, project_hitl_story
from policy.main import Decision, evaluate

TOKEN = "synthetic-hitl-viewer"
PATH = "/api/demo/explore-story/control"


class HitlStoryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def request(self, cursor=0, mode="story", token=TOKEN, action="start"):
        return self.client.post(PATH, json={"action": action, "cursor": cursor, "mode": mode},
                                headers={"Authorization": "Bearer " + token})

    def test_approval_dryrun_postchecks_recovery_are_honestly_unverified(self):
        model = build_acme_impact_read_model()
        for cue, cursor in (("approve", 5), ("simulate", 6),
                            ("verify", 7), ("close", 8)):
            with self.subTest(cue=cue):
                action = "pause" if cursor == 8 else "start"  # start at last cue intentionally rewinds
                a, b = self.request(cursor, "story", action=action), self.request(cursor, "explore", action=action)
                self.assertEqual(a.status_code, 200)
                self.assertEqual(b.status_code, 200)
                self.assertEqual(a.json()["hitl_story"], b.json()["hitl_story"])
                h = a.json()["hitl_story"]
                self.assertEqual(h["story_state"], STATES[cue])
                self.assertEqual(h["run_id"], model["run_id"])
                self.assertEqual(h["incident_id"], model["incident_id"])
                self.assertEqual(h["impact_incident_id"], model["impact_incident_id"])
                self.assertEqual(h["human_decision"], "NOT_AUTHENTICATED")
                self.assertEqual(h["temporal_workflow"], "NOT_EXECUTED")
                self.assertEqual(h["postchecks"], "NOT_EXECUTED")
                self.assertEqual(h["recovery"], "NOT_VERIFIED")
                self.assertEqual(h["policy_command"], "OBSERVE")
                self.assertFalse(h["policy_runtime_checked"])
                self.assertFalse(h["live_effect_authorized"])
                self.assertIsNone(h["approval_id"])
                self.assertIsNone(h["dry_run_receipt"])
                self.assertEqual(a.headers["cache-control"], "no-store")

    def test_no_backend_calls_and_repeatable_read_only_story(self):
        with patch.object(main, "post_json", side_effect=AssertionError("backend write")), patch.object(
            main, "get_json", side_effect=AssertionError("backend read")
        ):
            a, b = self.request(5), self.request(5)
        self.assertEqual(a.status_code, 200)
        self.assertEqual(a.json(), b.json())

    def test_refuse_unauthenticated_before_fixture_read(self):
        with patch("portal.acme_explore_story._load_or_503",
                   side_effect=AssertionError("fixture read")) as load:
            for token in ("wrong", ""):
                self.assertEqual(self.request(5, token=token).status_code, 401)
            load.assert_not_called()

    def test_reject_forged_binding_or_policy_preview_without_leak(self):
        model = build_acme_impact_read_model()
        for mutation in (
            lambda m: m.update(run_id="RUN-OTHER"),
            lambda m: m.update(incident_id="OTHER-TENANT"),
            lambda m: m.update(runtime_attested=True),
            lambda m: m["decision_preview"]["policy"].update(decision="ALLOW"),
            lambda m: m["decision_preview"].update(backend_writes=True),
        ):
            altered = copy.deepcopy(model)
            mutation(altered)
            with self.subTest(altered=altered["run_id"]), patch(
                "portal.acme_explore_story._load_or_503", return_value=altered
            ):
                response = self.request(5)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["state"], "UNKNOWN")
                self.assertNotIn("RUN-OTHER", response.text)

    def test_policy_actual_unit_evaluator_rejects_live_even_with_boolean_approval(self):
        decision = Decision(mode="LIVE", command="REMEDIATE", severity="P2",
                            confidence=1.0, evidence_count=4, critic_validated=True,
                            redundancy_ok=True, evidence_fresh=True,
                            preconditions_verified=True, fencing_verified=True,
                            human_approved=True)
        result = evaluate(decision)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["decision"], "HUMAN_APPROVAL")
        self.assertEqual(evaluate(decision.model_copy(update={
            "mode": "DEMO", "command": "OBSERVE"}))["decision"], "SIMULATE")

    def test_invalid_story_cue_and_corrupted_model_fail_closed(self):
        model = build_acme_impact_read_model()
        for cue in ("LIVE", "execute", "", None):
            with self.subTest(cue=cue), self.assertRaises(ValueError):
                project_hitl_story(model, cue)
        model["source_sha256"] = "not-a-digest"
        with self.assertRaises(ValueError):
            project_hitl_story(model, "approve")


if __name__ == "__main__":
    unittest.main()
