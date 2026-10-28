"""Unit-only contract tests; upstream Core/PostgreSQL integration NOT_TESTED here."""
import json
import os
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
        with patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, LEDGER]) as upstream:
            response = self.read("Bearer " + VIEWER)
        self.assertEqual(response.status_code, 200)
        result = payload(response)
        self.assertEqual(result["run_id"], RUN)
        self.assertEqual(result["classification"], "DEMO_CORE_RECORDED_NOT_LIVE")
        self.assertFalse(result["tenant_acl_qualified"])
        self.assertFalse(result["critiques"][0]["claim_checks"][0]["supported"])
        self.assertNotIn("MUST_NOT_LEAK", response.body.decode())
        self.assertNotIn(VIEWER, response.body.decode())
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(upstream.call_count, 2)
        self.assertEqual(upstream.call_args_list[1].args[1], "/api/runs/" + RUN + "/ai-ledger")

    def test_sourced_claim_requires_linked_analysis_and_evidence(self):
        valid = json.loads(json.dumps(LEDGER))
        valid["critiques"][0]["output"]["claim_checks"][0] = {
            "claim": "Synthetic SAN CRC", "supported": True,
            "supporting_evidence_ids": ["EVD-1"],
        }
        with patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, valid]):
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
                    "portal.demo_ledger_read.get_json", side_effect=[DETAIL, forged]):
                denied = self.read("Bearer " + VIEWER)
                self.assertEqual(denied.status_code, 503)
                self.assertEqual(payload(denied)["status"], "UNKNOWN")
                self.assertNotIn("EVD-NOT-SOURCED", denied.body.decode())
                self.assertEqual(denied.headers["cache-control"], "no-store")

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
            with self.subTest(ledger=ledger), patch("portal.demo_ledger_read.get_json", side_effect=[DETAIL, ledger]):
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
