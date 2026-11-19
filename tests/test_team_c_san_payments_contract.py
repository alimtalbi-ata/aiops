import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/contracts/team-c-san-payments-run-journey.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/team_c/run-journey.valid.json"
STAGES = (
    "capability_simulator", "capability_core", "capability_twin",
    "capability_policy", "capability_worker", "simulator_start",
    "pre_resolution_core", "pre_resolution_twin", "pre_resolution_policy",
    "pre_resolution_worker", "worker_no_effect", "core_finalization",
    "post_resolution_core", "post_resolution_twin", "post_resolution_policy",
    "post_resolution_worker", "resolved",
)

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def check_story_contract(value):
    assert value["schema"] == "aiops.team-c.san-payments-run-journey.v1"
    assert value["scope"] == "STORY_OFFLINE" and value["mode"] == "DEMO"
    run = value["run"]
    assert run["tenant_id"] is None and run["run_id"].startswith("SIM-ACME-")
    assert re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", run["attempt_id"])
    assert re.fullmatch(r"[0-9a-f]{40}", run["executed_sha"])
    assert run["idempotency_key"] == run["attempt_id"]
    assert run["scenario_id"] == "ACME-SAN-PAYMENTS"
    receipt = value["receipt"]
    assert receipt["schema"] == "aiops.debian-acme-sim-e2e.v1"
    assert re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"])
    assert receipt["reason"] == "SIMULATED_SANDBOX_ONLY"
    assert re.fullmatch(r"SIM-GLPI-[A-Za-z0-9][A-Za-z0-9_-]*", receipt["ticket_id"])
    assert tuple(receipt["stages"]) == STAGES
    assert all(receipt["stages"][stage] == "PASS" for stage in STAGES)
    assert len(value["stage_evidence"]) == 17
    stage_names = [item["stage"] for item in value["stage_evidence"]]
    assert len(stage_names) == len(set(stage_names)) == 17
    assert set(stage_names) == set(STAGES)
    for item in value["stage_evidence"]:
        assert item["status"] == "PASS"
        assert item["run_id"] == run["run_id"]
        assert item["attempt_id"] == run["attempt_id"]
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?Z", item["observed_at"])
    intel = value["intelligence"]
    assert intel["provider"] == "DETERMINISTIC_RULES_NOT_LLM"
    assert intel["analyst_status"] == "HYPOTHESIS_ONLY"
    assert intel["critic_disposition"] == "HOLD_FOR_HUMAN_REVIEW"
    assert intel["critic_independently_verified"] is False
    assert value["policy"]["decision"] == "DENY_LIVE_ACTION"
    assert value["policy"]["execution_allowed"] is False
    assert value["policy"]["effect_allowed"] is False
    assert value["hitl"]["approval_id"].startswith("SIM-APP-")
    assert value["hitl"]["issuer"] == "TWIN_ACME_SIMULATED"
    assert value["hitl"]["human_approval_claimed"] is False
    assert value["worker"]["executor"] == "TEMPORAL"
    assert value["worker"]["isolated"] is True and value["worker"]["no_effect"] is True
    assert value["worker"]["runtime_attested"] is False
    assert value["provenance"]["source_kind"] == "LOCAL_SYNTHETIC_FIXTURE"
    assert value["provenance"]["expected_sha"] == run["executed_sha"]
    assert value["provenance"]["collected_at"].endswith("Z")

class TeamCSanPaymentsContractTests(unittest.TestCase):
    def setUp(self):
        self.value = load(FIXTURE_PATH)

    def test_positive_story_offline_contract(self):
        check_story_contract(self.value)

    def test_schema_is_closed_and_requires_17_stages(self):
        schema = load(SCHEMA_PATH)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["schema"]["const"], "aiops.team-c.san-payments-run-journey.v1")
        receipt_stages = schema["properties"]["receipt"]["properties"]["stages"]
        self.assertFalse(receipt_stages["additionalProperties"])
        self.assertEqual(set(receipt_stages["required"]), set(STAGES))
        self.assertEqual(len(receipt_stages["required"]), 17)

    def test_rejects_live_mode(self):
        self.value["mode"] = "LIVE"
        with self.assertRaises((AssertionError, KeyError, TypeError)):
            check_story_contract(self.value)

    def test_rejects_fixture_to_runtime_tenant_promotion(self):
        self.value["run"]["tenant_id"] = "ACME-TEST"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_real_ticket_identifier(self):
        self.value["receipt"]["ticket_id"] = "GLPI-1234"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_human_approval_claim(self):
        self.value["hitl"]["human_approval_claimed"] = True
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_policy_bypass(self):
        self.value["policy"]["effect_allowed"] = True
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_stage_identity_drift(self):
        self.value["stage_evidence"][4]["attempt_id"] = "ACME-SIM-FFFFFFFFFFFFFFFF"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_missing_stage(self):
        self.value["stage_evidence"].pop()
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_duplicate_stage(self):
        self.value["stage_evidence"][0]["stage"] = self.value["stage_evidence"][1]["stage"]
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_non_utc_timestamp(self):
        self.value["stage_evidence"][0]["observed_at"] = "2026-11-19T15:00:00+01:00"
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

    def test_rejects_runtime_claim_from_fixture(self):
        self.value["worker"]["runtime_attested"] = True
        with self.assertRaises(AssertionError):
            check_story_contract(self.value)

if __name__ == "__main__":
    unittest.main()
