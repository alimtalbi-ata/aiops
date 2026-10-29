"""Offline synthetic cross-receipt contract fixtures; NOT actual E2E or Debian."""
from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_demo_evidence_receipts import Blocked, load_local_json, main, qualify


def fixture():
    rid = "RUN-DEMO-1"
    item = {"evidence_id": "EVD-1", "source": "synthetic.acme.san",
            "payload_sha256": "a" * 64, "known_at": datetime.now(timezone.utc).isoformat()}
    refs = {"schema": "aiops.core-demo-evidence-refs.v1", "run_id": rid,
            "classification": "SYNTHETIC_ONLY", "tenant_acl_qualified": False,
            "runtime_attested": False, "event_link_verified": True, "items": [item]}
    ledger = {"schema": "aiops.demo-ledger-read.v1", "run_id": rid, "mode": "DEMO",
              "classification": "DEMO_CORE_RECORDED_NOT_LIVE", "source": "CORE_AI_LEDGER_INTERNAL_READ",
              "tenant_acl_qualified": False, "runtime_attested": False,
              "evidence_classification": "SYNTHETIC_ONLY", "event_link_verified": True,
              "evidence_refs": [deepcopy(item)],
              "analyses": [{"analysis_id": "A-1", "model": "synthetic", "status": "COMPLETE",
                            "evidence_ids": ["EVD-1"]}],
              "critiques": [{"critique_id": "C-1", "analysis_id": "A-1", "model": "synthetic",
                             "validated": True, "evidence_ids": ["EVD-1"], "claim_checks": [
                                 {"claim": "synthetic", "supported": True,
                                  "supporting_evidence_ids": ["EVD-1"]}]}],
              "policy_decisions": [{"policy_decision_id": "P-1", "decision": "SIMULATE",
                                    "state": "PASS"}]}
    return rid, ledger, refs


class EvidenceReceiptTests(unittest.TestCase):
    def test_positive_is_still_no_go(self):
        rid, ledger, refs = fixture()
        result = qualify(rid, ledger, refs)
        self.assertEqual(result["assessment"], "REFERENTIAL_CHECK_PASS")
        self.assertEqual(result["overall"], "NO_GO")
        for key in ("incident_id_correlation", "tenant_rbac", "temporal_execution",
                    "independent_evidence_validation", "debian_deployment_and_rollback"):
            self.assertEqual(result[key], "NOT_TESTED")

    def test_fail_closed_identity_provenance_and_policy(self):
        mutations = [
            ("run_id", "RUN-OTHER"), ("mode", "LIVE"),
            ("classification", "OBSERVED_LIVE"), ("tenant_acl_qualified", True),
            ("runtime_attested", True), ("event_link_verified", False),
        ]
        for key, value in mutations:
            rid, ledger, refs = fixture()
            ledger[key] = value
            with self.subTest(key=key), self.assertRaises(Blocked):
                qualify(rid, ledger, refs)
        for decision in ("ALLOW", "EXECUTE", "REMEDIATE", "SIMULATE_LIVE"):
            rid, ledger, refs = fixture()
            ledger["policy_decisions"][0]["decision"] = decision
            with self.subTest(decision=decision), self.assertRaises(Blocked):
                qualify(rid, ledger, refs)

    def test_cross_receipt_and_analysis_linkage_refused(self):
        rid, ledger, refs = fixture()
        refs["items"][0]["payload_sha256"] = "b" * 64
        with self.assertRaises(Blocked):
            qualify(rid, ledger, refs)
        rid, ledger, refs = fixture()
        ledger["analyses"][0]["evidence_ids"] = ["EVD-OTHER"]
        with self.assertRaises(Blocked):
            qualify(rid, ledger, refs)
        rid, ledger, refs = fixture()
        ledger["critiques"][0]["evidence_ids"] = ["EVD-OTHER"]
        with self.assertRaises(Blocked):
            qualify(rid, ledger, refs)
        rid, ledger, refs = fixture()
        ledger["critiques"][0]["claim_checks"][0]["supporting_evidence_ids"] = ["EVD-OTHER"]
        with self.assertRaises(Blocked):
            qualify(rid, ledger, refs)

    def test_refs_provenance_hash_timestamp_and_duplicate_refused(self):
        for key, value in (("classification", "LIVE"), ("tenant_acl_qualified", True),
                           ("runtime_attested", True), ("event_link_verified", False)):
            rid, ledger, refs = fixture()
            refs[key] = value
            with self.subTest(key=key), self.assertRaises(Blocked):
                qualify(rid, ledger, refs)
        for key, value in (("payload_sha256", "bad"), ("known_at", "2026-01-01T00:00:00"),
                           ("source", "invalid source")):
            rid, ledger, refs = fixture()
            refs["items"][0][key] = value
            with self.subTest(key=key), self.assertRaises(Blocked):
                qualify(rid, ledger, refs)
        rid, ledger, refs = fixture()
        refs["items"].append(deepcopy(refs["items"][0]))
        with self.assertRaises(Blocked):
            qualify(rid, ledger, refs)

    def test_core_reference_limit_80_not_50(self):
        rid, ledger, refs = fixture()
        for index in range(2, 52):
            item = deepcopy(refs["items"][0])
            item["evidence_id"] = f"EVD-{index}"
            refs["items"].append(item)
            ledger["evidence_refs"].append(deepcopy(item))
            ledger["analyses"][0]["evidence_ids"].append(item["evidence_id"])
            ledger["critiques"][0]["evidence_ids"].append(item["evidence_id"])
        self.assertEqual(qualify(rid, ledger, refs)["overall"], "NO_GO")
        for index in range(52, 82):
            item = deepcopy(refs["items"][0])
            item["evidence_id"] = f"EVD-{index}"
            refs["items"].append(item)
        with self.assertRaises(Blocked):
            qualify(rid, ledger, refs)

    def test_missing_simulate_pass_refused(self):
        rid, ledger, refs = fixture()
        ledger["policy_decisions"][0]["state"] = "BLOCKED"
        with self.assertRaises(Blocked):
            qualify(rid, ledger, refs)

    def test_simulate_pass_with_only_unvalidated_critique_is_blocked(self):
        rid, ledger, refs = fixture()
        ledger["critiques"][0]["validated"] = False
        with self.assertRaisesRegex(Blocked, "simulate_pass_without_validated_critique"):
            qualify(rid, ledger, refs)

    def test_validated_critique_is_necessary_not_independent_policy_proof(self):
        rid, ledger, refs = fixture()
        ledger["critiques"].append({
            "critique_id": "C-2", "analysis_id": "A-1", "model": "synthetic",
            "validated": False, "evidence_ids": ["EVD-1"], "claim_checks": [],
        })
        receipt = qualify(rid, ledger, refs)
        self.assertEqual(receipt["assessment"], "REFERENTIAL_CHECK_PASS")
        self.assertEqual(receipt["policy_critic_linkage_origin"], "NOT_TESTED")
        self.assertEqual(receipt["overall"], "NO_GO")

    def test_local_files_cli_redacts_and_blocks_symlinks(self):
        rid, ledger, refs = fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lp, rp = root / "ledger.json", root / "refs.json"
            lp.write_text(json.dumps(ledger))
            rp.write_text(json.dumps(refs))
            args = ["--run-id", rid, "--ledger-file", str(lp), "--refs-file", str(rp)]
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(output.getvalue())["overall"], "NO_GO")
            self.assertNotIn("EVD-1", output.getvalue())
            self.assertNotIn(str(lp), output.getvalue())
            link = root / "link.json"
            link.symlink_to(lp)
            with self.assertRaises(Blocked):
                load_local_json(link)
            rp.write_text('{"schema":"x","schema":"y"}')
            with self.assertRaises(Blocked):
                load_local_json(rp)
            rp.write_bytes(b"x" * 131073)
            with self.assertRaises(Blocked):
                load_local_json(rp)


if __name__ == "__main__":
    unittest.main()


# The existing quality.yml Evidence test step also covers the P0 aggregate gate.
from datetime import timedelta
from scripts.check_demo_release_receipts import qualify_release, main as release_main


def release_fixture():
    rid, ledger, refs = fixture()
    stable, candidate = "a" * 40, "b" * 40
    coverage = {
        "schema": "aiops.demo-stable-deployment-coverage.v1",
        "stable_sha": stable, "candidate_sha": candidate,
        "assessment": "READY_FOR_REVIEW", "overall": "NO_GO",
        "provenance": "OFFLINE_GIT_DIFF_NOT_RUNTIME",
        "unsupported_count": 0, "unsupported_paths": [],
        "changed_count": 1,
        "module_deployment_matrix": [{
            "path": "app/portal/demo_v2.py", "git_status": "M",
            "decision": "REVIEWABLE",
        }],
        "field_smoke_tests": "NOT_TESTED", "rollback_test": "NOT_TESTED",
    }
    field = {
        "schema": "aiops.demo-field-readonly-preflight.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "assessment": "READONLY_PREFLIGHT_PASS", "overall": "NO_GO",
        "provenance": "OPERATOR_LOCAL_READONLY_OBSERVATION_UNATTESTED",
        "applied_sha_verified": "MATCH_UNATTESTED",
        "checks": {name: "PASS" for name in (
            "core_health", "twin_health", "copilot_health", "portal_health",
            "core_anonymous_noc_denied", "portal_demo_studio_readable",
            "local_applied_sha_consistency",
        )},
        "tenant_rbac": "NOT_TESTED",
        "core_temporal_analyst_critic_policy_evidence": "NOT_TESTED",
        "run_incident_evidence_correlation": "NOT_TESTED",
        "twin_payments_impact": "NOT_TESTED", "rollback_verified": "NOT_TESTED",
    }
    return stable, candidate, rid, coverage, field, ledger, refs


class ReleaseAggregateTests(unittest.TestCase):
    def test_aggregate_never_approves_stable_or_e2e(self):
        receipt = qualify_release(*release_fixture())
        self.assertEqual(receipt["assessment"], "REVIEWABLE_UNATTESTED")
        self.assertEqual(receipt["overall"], "NO_GO")
        self.assertEqual(receipt["ready_for_stable"], "BLOCKED")
        self.assertEqual(receipt["checks"]["local_applied_sha_match_only"], "PASS_UNATTESTED")
        for key in ("run_incident_field_linkage", "tenant_rbac",
                    "payments_runtime_impact", "debian_applied_sha_attestation",
                    "debian_rollback", "policy_critic_origin"):
            self.assertEqual(receipt[key], "NOT_TESTED")

    def test_aggregate_blocks_unsafe_or_stale_receipts(self):
        for index in range(10):
            args = list(release_fixture())
            if index == 0:
                args[3]["unsupported_count"] = 1
            elif index == 1:
                args[3]["module_deployment_matrix"][0]["decision"] = "BLOCKED"
            elif index == 2:
                args[3]["candidate_sha"] = "c" * 40
            elif index == 3:
                args[4]["checks"]["core_anonymous_noc_denied"] = "BLOCKED"
            elif index == 4:
                args[4]["applied_sha_verified"] = "NOT_TESTED"
            elif index == 5:
                args[4]["timestamp_utc"] = (
                    datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            elif index == 6:
                args[4]["timestamp_utc"] = (
                    datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            elif index == 7:
                args[5]["run_id"] = "OTHER-RUN"
            elif index == 8:
                args[6]["items"][0]["payload_sha256"] = "0" * 64
            else:
                args[4]["overall"] = "GO"
            with self.subTest(case=index), self.assertRaises(Blocked):
                qualify_release(*args)

    def test_aggregate_cli_redacts_and_fails_closed(self):
        stable, candidate, rid, coverage, field, ledger, refs = release_fixture()
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for name, data in zip(("coverage", "field", "ledger", "refs"),
                                  (coverage, field, ledger, refs)):
                path = Path(folder) / (name + ".json")
                path.write_text(json.dumps(data))
                paths.extend(["--" + name + "-file", str(path)])
            args = ["--stable-sha", stable, "--candidate-sha", candidate,
                    "--run-id", rid] + paths
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(release_main(args), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["overall"], "NO_GO")
            self.assertNotIn("EVD-1", output.getvalue())
            self.assertNotIn(folder, output.getvalue())
            field["checks"]["portal_health"] = "BLOCKED"
            (Path(folder) / "field.json").write_text(json.dumps(field))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(release_main(args), 2)
            self.assertEqual(json.loads(output.getvalue())["assessment"], "BLOCKED")
            self.assertNotIn(folder, output.getvalue())
