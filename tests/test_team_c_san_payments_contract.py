import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/contracts/team-c-san-payments-run-journey.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/team_c/run-journey.valid.json"
STAGES = ["capability_simulator","capability_core","capability_twin","capability_policy","capability_worker","simulator_start","pre_resolution_core","pre_resolution_twin","pre_resolution_policy","pre_resolution_worker","worker_no_effect","core_finalization","post_resolution_core","post_resolution_twin","post_resolution_policy","post_resolution_worker","resolved"]

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def check_story_contract(value):
    assert value["schema"] == "aiops.team-c.san-payments-run-journey.v2"
    assert value["scope"] == "STORY_OFFLINE" and value["mode"] == "DEMO"
    run = value["run"]
    assert re.fullmatch(r"SIM-ACME-[A-F0-9]{16}", run["run_id"])
    assert re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", run["attempt_id"])
    assert run["tenant_id"] is None and run["executed_sha"] is None
    assert run["idempotency_key"] == run["attempt_id"]
    assert run["scenario_id"] == "ACME-SAN-PAYMENTS"
    assert value["receipt"] is None
    assert value["hitl"]["kind"] == "SIMULATED_NOT_REQUESTED"
    assert value["hitl"]["approval_id"] is None
    assert value["hitl"]["human_approval_claimed"] is False
    assert value["worker"]["executor"] == "NOT_INVOKED"
    assert value["worker"]["runtime_attested"] is False
    assert value["policy"]["decision"] == "DENY_LIVE_ACTION"
    assert value["policy"]["execution_allowed"] is False
    assert value["policy"]["effect_allowed"] is False
    assert value["intelligence"]["provider"] == "DETERMINISTIC_RULES_NOT_LLM"
    assert value["intelligence"]["critic_independently_verified"] is False
    plan = value["stage_plan"]
    assert len(plan) == 17
    names = [item["stage"] for item in plan]
    assert len(set(names)) == 17 and set(names) == set(STAGES)
    for item in plan:
        assert item["status"] == "NOT_RUN" and item["evidence_state"] == "MISSING"
        assert item["run_id"] == run["run_id"]
        assert item["attempt_id"] == run["attempt_id"]
        assert item["sha256"] is None and item["observed_at"] is None
    provenance = value["provenance"]
    assert provenance["source_kind"] == "LOCAL_SYNTHETIC_FIXTURE"
    assert provenance["source_git_sha"] is None
    assert provenance["expected_sha"] is None
    assert provenance["collected_at"] is None

class TeamCSanPaymentsContractTests(unittest.TestCase):
    def setUp(self):
        self.value = load(FIXTURE_PATH)

    def test_positive_offline_projection_is_not_an_execution_receipt(self):
        check_story_contract(self.value)

    def test_schema_is_closed_and_has_exact_17_stage_plan(self):
        schema = load(SCHEMA_PATH)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["schema"]["const"], "aiops.team-c.san-payments-run-journey.v2")
        self.assertEqual(schema["properties"]["stage_plan"]["minItems"], 17)
        self.assertEqual(schema["properties"]["stage_plan"]["maxItems"], 17)
        self.assertEqual(schema["properties"]["receipt"]["type"], "null")

    def test_rejects_live_mode(self):
        self.value["mode"] = "LIVE"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_tenant_promotion(self):
        self.value["run"]["tenant_id"] = "ACME-TEST"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_fabricated_executed_sha(self):
        self.value["run"]["executed_sha"] = "a" * 40
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_fabricated_receipt(self):
        self.value["receipt"] = {"status": "PASS"}
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_human_approval_claim(self):
        self.value["hitl"]["human_approval_claimed"] = True
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_worker_invocation_claim(self):
        self.value["worker"]["executor"] = "TEMPORAL"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_policy_bypass(self):
        self.value["policy"]["effect_allowed"] = True
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_stage_identity_drift(self):
        self.value["stage_plan"][4]["attempt_id"] = "ACME-SIM-FFFFFFFFFFFFFFFF"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_missing_or_duplicate_stage(self):
        self.value["stage_plan"].pop()
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)
        self.setUp()
        self.value["stage_plan"][0]["stage"] = self.value["stage_plan"][1]["stage"]
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_false_evidence_state(self):
        self.value["stage_plan"][0]["status"] = "PASS"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

if __name__ == "__main__":
    unittest.main()
