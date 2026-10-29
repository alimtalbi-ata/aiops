"""Unit-only contract tests; upstream Core/PostgreSQL integration NOT_TESTED here."""
import json
import os
from datetime import datetime, timedelta, timezone
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-only-internal-token-32-characters"}):
    from portal.demo_ledger_read import read_demo_ledger

VIEWER = "ci-only-viewer-token-32-characters"
RUN = "RUN-DEMO-1"
DETAIL = {"run": {"run_id": RUN, "mode": "DEMO", "status": "RESOLVED"}, "events": []}
LEDGER = {"run_id": RUN,
          "analyses": [{"analysis_id": "ANA-1", "model": "test-provider", "status": "VALID",
                        "evidence_ids": ["EVD-1"], "output": {"private_prompt": "MUST_NOT_LEAK"}}],
          "critiques": [{"critique_id": "CRT-1", "analysis_id": "ANA-1", "model": "test-provider",
                         "validated": False, "evidence_ids": ["EVD-1"],
                         "output": {"claim_checks": [{"claim": "CRC?", "supported": False,
                                                      "supporting_evidence_ids": []}]}}],
          "policy_decisions": []}

REFS = {"schema": "aiops.core-demo-evidence-refs.v1", "run_id": RUN,
        "classification": "SYNTHETIC_ONLY", "tenant_acl_qualified": False,
        "runtime_attested": False, "event_link_verified": True,
        "items": [{"evidence_id": "EVD-1", "source": "CI_SYNTHETIC_SAN",
                   "payload_sha256": "a" * 64,
                   "known_at": "2026-10-28T21:00:00+00:00"}]}


def payload(response):
    return json.loads(response.body)


class DemoLedgerReadTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-only-internal-token-32-characters",
                                        "AIOPS_PORTAL_READ_TOKEN": VIEWER})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def read(self, auth=None):
        return read_demo_ledger(RUN, authorization=auth)

    def test_auth_denies_before_upstream_io(self):
        with patch("portal.demo_ledger_read.get_json", side_effect=AssertionError("I/O before auth")) as call:
            for header in (None, "Basic " + VIEWER, "Bearer wrong", "Bearer "):
                self.assertEqual(self.read(header).status_code, 401)
            call.assert_not_called()

    def test_missing_or_shared_viewer_secret_fails_closed(self):
        with patch("portal.demo_ledger_read.get_json", side_effect=AssertionError("I/O before config")) as call:
            for value in ("", "short", "ci-only-internal-token-32-characters"):
                with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": value}):
                    self.assertEqual(self.read("Bearer " + VIEWER).status_code, 503)
            call.assert_not_called()

    def test_project_source_bound_and_no_private_payload(self):
        with patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, LEDGER, REFS]) as upstream:
            response = self.read("Bearer " + VIEWER)
        self.assertEqual(response.status_code, 200)
        result = payload(response)
        self.assertEqual(result["run_id"], RUN)
        self.assertEqual(result["classification"], "DEMO_CORE_RECORDED_NOT_LIVE")
        self.assertFalse(result["tenant_acl_qualified"])
        self.assertEqual(result["evidence_classification"], "SYNTHETIC_ONLY")
        self.assertEqual(result["evidence_refs"][0]["evidence_id"], "EVD-1")
        self.assertTrue(result["event_link_verified"])
        self.assertFalse(result["critiques"][0]["claim_checks"][0]["supported"])
        self.assertNotIn("MUST_NOT_LEAK", response.body.decode())
        self.assertNotIn(VIEWER, response.body.decode())
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(upstream.call_count, 3)
        self.assertEqual(upstream.call_args_list[1].args[1], "/api/runs/" + RUN + "/ai-ledger")
        self.assertEqual(upstream.call_args_list[2].args[1], "/api/noc/runs/" + RUN + "/evidence-refs")

    def test_sourced_claim_requires_linked_analysis_and_evidence(self):
        valid = json.loads(json.dumps(LEDGER))
        valid["critiques"][0]["output"]["claim_checks"][0] = {
            "claim": "Synthetic SAN CRC", "supported": True,
            "supporting_evidence_ids": ["EVD-1"],
        }
        with patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, valid, REFS]):
            response = self.read("Bearer " + VIEWER)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload(response)["critiques"][0]["claim_checks"][0]
                         ["supporting_evidence_ids"], ["EVD-1"])

        mutations = [
            ("dangling_analysis", lambda x: x["critiques"][0].update(analysis_id="ANA-OTHER")),
            ("duplicate_analysis", lambda x: x["analyses"].append(dict(x["analyses"][0]))),
            ("duplicate_critique", lambda x: x["critiques"].append(dict(x["critiques"][0]))),
            ("unsupported_claim", lambda x: x["critiques"][0]["output"]
             ["claim_checks"][0].update(supporting_evidence_ids=[])),
            ("unknown_evidence", lambda x: x["critiques"][0]["output"]
             ["claim_checks"][0].update(supporting_evidence_ids=["EVD-NOT-SOURCED"])),
            ("not_in_analysis", lambda x: x["critiques"][0].update(
                evidence_ids=["EVD-1", "EVD-NOT-SOURCED"])),
            ("not_in_critique", lambda x: x["critiques"][0].update(evidence_ids=[])),
        ]
        for name, mutate in mutations:
            forged = json.loads(json.dumps(valid))
            mutate(forged)
            if name == "not_in_analysis":
                forged["critiques"][0]["output"]["claim_checks"][0][
                    "supporting_evidence_ids"] = ["EVD-NOT-SOURCED"]
            with self.subTest(name=name), patch(
                    "portal.demo_ledger_read.get_json", side_effect=[DETAIL, forged, REFS]):
                denied = self.read("Bearer " + VIEWER)
                self.assertEqual(denied.status_code, 503)
                self.assertEqual(payload(denied)["status"], "UNKNOWN")
                self.assertNotIn("EVD-NOT-SOURCED", denied.body.decode())
                self.assertEqual(denied.headers["cache-control"], "no-store")

    def test_cross_analysis_evidence_swap_fails_closed_even_without_supported_claim(self):
        # Run-wide union remains EVD-1/EVD-2, so Core's union check alone
        # cannot detect a Critique that borrows another Analysis' evidence.
        multi = json.loads(json.dumps(LEDGER))
        multi["analyses"].append({**multi["analyses"][0],
                                  "analysis_id": "ANA-2", "evidence_ids": ["EVD-2"]})
        multi["critiques"].append({**multi["critiques"][0],
                                   "critique_id": "CRT-2", "analysis_id": "ANA-2",
                                   "evidence_ids": ["EVD-2"]})
        refs = json.loads(json.dumps(REFS))
        refs["items"].append({**refs["items"][0], "evidence_id": "EVD-2"})
        with patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, multi, refs]):
            self.assertEqual(self.read("Bearer " + VIEWER).status_code, 200)
        # Neither Critique claims support: this still must be rejected.
        multi["critiques"][0]["evidence_ids"] = ["EVD-2"]
        multi["critiques"][1]["evidence_ids"] = ["EVD-1"]
        with patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, multi, refs]):
            denied = self.read("Bearer " + VIEWER)
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(payload(denied), {"status": "UNKNOWN",
                                           "reason": "ledger_unavailable"})
        self.assertEqual(denied.headers["cache-control"], "no-store")
        for identifier in ("ANA-2", "CRT-2", "EVD-2", VIEWER):
            self.assertNotIn(identifier, denied.body.decode())


    def test_policy_decisions_require_same_run_analysis_and_critique(self):
        valid = json.loads(json.dumps(LEDGER))
        # Two analyses on one Run; a decision cannot mix their links.
        valid["analyses"].append({**valid["analyses"][0], "analysis_id": "ANA-2"})
        valid["critiques"].append({**valid["critiques"][0],
                                   "critique_id": "CRT-2", "analysis_id": "ANA-2"})
        valid["policy_decisions"] = [
            {"policy_decision_id": "POL-1", "analysis_id": "ANA-1",
             "critique_id": "CRT-1", "decision": "SIMULATE", "state": "PASS"},
            {"policy_decision_id": "POL-2", "analysis_id": "ANA-2",
             "critique_id": None, "decision": "BLOCK", "state": "BLOCKED"},
            {"policy_decision_id": "POL-3", "analysis_id": None,
             "critique_id": "CRT-2", "decision": "OBSERVE", "state": "PASS"},
        ]
        with patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, valid, REFS]):
            allowed = self.read("Bearer " + VIEWER)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual([x["policy_decision_id"] for x in payload(allowed)["policy_decisions"]],
                         ["POL-1", "POL-2", "POL-3"])

        def change_policy(ledger, **fields):
            ledger["policy_decisions"][0].update(fields)

        mutations = [
            ("foreign_analysis", lambda x: change_policy(x, analysis_id="ANA-FOREIGN")),
            ("foreign_critique", lambda x: change_policy(x, critique_id="CRT-FOREIGN")),
            ("cross_analysis", lambda x: change_policy(x, analysis_id="ANA-2")),
            ("no_link", lambda x: change_policy(x, analysis_id=None, critique_id=None)),
            ("duplicate", lambda x: x["policy_decisions"].append(
                dict(x["policy_decisions"][0]))),
            ("live_allow", lambda x: change_policy(x, decision="ALLOW")),
            ("live_execute", lambda x: change_policy(x, decision="EXECUTE")),
            ("live_remediate", lambda x: change_policy(x, decision="REMEDIATE")),
            ("unrecognized", lambda x: change_policy(x, decision="UNKNOWN_ACTION")),
            ("unrecognized_state", lambda x: change_policy(x, state="APPLIED")),
        ]
        for name, mutate in mutations:
            forged = json.loads(json.dumps(valid))
            mutate(forged)
            with self.subTest(name=name), patch(
                    "portal.demo_ledger_read.get_json", side_effect=[DETAIL, forged, REFS]):
                denied = self.read("Bearer " + VIEWER)
            self.assertEqual(denied.status_code, 503)
            self.assertEqual(payload(denied), {"status": "UNKNOWN",
                                               "reason": "ledger_unavailable"})
            self.assertEqual(denied.headers["cache-control"], "no-store")
            for private in ("ANA-FOREIGN", "CRT-FOREIGN", "POL-1", VIEWER):
                self.assertNotIn(private, denied.body.decode())

    def test_resolver_required_even_when_ledger_links_are_consistent(self):
        mutations = [
            ("absent", {}),
            ("wrong_run", {**REFS, "run_id": "RUN-OTHER"}),
            ("wrong_mode", {**REFS, "classification": "OBSERVED"}),
            ("runtime_claim", {**REFS, "runtime_attested": True}),
            ("tenant_claim", {**REFS, "tenant_acl_qualified": True}),
            ("no_event", {**REFS, "event_link_verified": False}),
            ("empty", {**REFS, "items": []}),
            ("missing_id", {**REFS, "items": [{**REFS["items"][0], "evidence_id": "EVD-OTHER"}]}),
            ("bad_hash", {**REFS, "items": [{**REFS["items"][0], "payload_sha256": "broken"}]}),
            ("bad_time", {**REFS, "items": [{**REFS["items"][0], "known_at": "2026-10-28"}]}),
            ("future_time", {**REFS, "items": [{**REFS["items"][0],
                "known_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}]}),
            ("tenant_metadata", {**REFS, "ownerTenantId": "TENANT-B"}),
            ("extra_payload", {**REFS, "items": [{**REFS["items"][0], "payload": "private"}]}),
            ("duplicate", {**REFS, "items": REFS["items"] * 2}),
        ]
        for name, refs in mutations:
            with self.subTest(name=name), patch(
                    "portal.demo_ledger_read.get_json", side_effect=[DETAIL, LEDGER, refs]):
                denied = self.read("Bearer " + VIEWER)
                self.assertEqual(denied.status_code, 503)
                self.assertEqual(payload(denied), {"status": "UNKNOWN",
                                                   "reason": "ledger_unavailable"})
                self.assertEqual(denied.headers["cache-control"], "no-store")
                self.assertNotIn("TENANT-B", denied.body.decode())

    def test_resolver_core_401_fails_closed(self):
        from requests import HTTPError
        with patch("portal.demo_ledger_read.get_json",
                   side_effect=[DETAIL, LEDGER, HTTPError("private Core 401")]):
            denied = self.read("Bearer " + VIEWER)
        self.assertEqual(denied.status_code, 503)
        self.assertNotIn("private", denied.body.decode())

    def test_core_401_fails_closed_without_leak(self):
        from requests import HTTPError
        with patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, HTTPError("Bearer SECRET core 401")]):
            response = self.read("Bearer " + VIEWER)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("SECRET", response.body.decode())

    def test_live_and_wrong_run_denied_before_ledger_io(self):
        for detail in ({"run": {"run_id": RUN, "mode": "LIVE"}},
                       {"run": {"run_id": "RUN-OTHER", "mode": "DEMO"}}):
            with self.subTest(detail=detail), patch("portal.demo_ledger_read.get_json", return_value=detail) as upstream:
                self.assertEqual(self.read("Bearer " + VIEWER).status_code, 503)
                upstream.assert_called_once()

    def test_missing_ledger_and_cross_tenant_denied(self):
        for ledger in ({}, {**LEDGER, "run_id": "RUN-OTHER"},
                       {**LEDGER, "analyses": [{**LEDGER["analyses"][0], "ownerTenantId": "A"}]},
                       {**LEDGER, "critiques": [{**LEDGER["critiques"][0], "output": {"claim_checks": []}, "orgRef": None}]},
                       {**LEDGER, "analyses": [{**LEDGER["analyses"][0], "evidence_ids": ["EVD-1", "EVD-1"]}]}):
            with self.subTest(ledger=ledger), patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, ledger, REFS]):
                self.assertEqual(self.read("Bearer " + VIEWER).status_code, 503)

    def test_detail_tenant_denied_before_ledger_io(self):
        with patch("portal.demo_ledger_read.get_json", return_value={**DETAIL, "accountRef": None}) as upstream:
            self.assertEqual(self.read("Bearer " + VIEWER).status_code, 503)
            upstream.assert_called_once()

    def test_invalid_id_never_contacts_core(self):
        with patch("portal.demo_ledger_read.get_json", side_effect=AssertionError("unexpected I/O")):
            self.assertEqual(read_demo_ledger("../../other", authorization="Bearer " + VIEWER).status_code, 503)

    def test_viewer_secret_is_wired_separately_for_new_installs(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn('AIOPS_PORTAL_READ_TOKEN: ${AIOPS_PORTAL_READ_TOKEN:-}',
                      (root / 'compose.yml').read_text())
        self.assertIn('AIOPS_PORTAL_READ_TOKEN=',
                      (root / 'config/.env.example').read_text())
        self.assertIn('set_value AIOPS_PORTAL_READ_TOKEN "$(openssl rand -hex 32)"',
                      (root / 'deploy/init-env.sh').read_text())

    def test_legacy_portal_does_not_expose_ledger_anonymously(self):
        source = (Path(__file__).resolve().parents[1] / "app/portal/main.py").read_text()
        self.assertNotIn('ledger=_get("/api/runs/"+key+"/ai-ledger")', source)
        self.assertNotIn('ledger=_get("/api/runs/"+rid+"/ai-ledger")', source)
        self.assertIn("app.include_router(demo_ledger_router)", source)


if __name__ == "__main__":
    unittest.main()
