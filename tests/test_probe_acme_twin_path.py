"""No-network contracts for the authenticated, read-only Twin path probe."""
import importlib.util
import io
import json
import os
from pathlib import Path
from unittest import TestCase, main, mock
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location("twin_probe", Path(__file__).resolve().parents[1] / "tools/probe_acme_twin_path.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def payload():
    chain = [probe.ROOT, "ACME-STO-PURE01", "ACME-VM-PAY01", "ACME-APP-ORACLEPAY",
             "ACME-SVC-PAYMENTS", "ACME-BIZ-PAYMENTS"]
    return {"root": probe.ROOT, "path_semantics": "SEEDED_TOPOLOGY_SHORTEST_HOPS_NOT_RUNTIME_CAUSALITY",
            "traversal_direction": "REVERSE_CONSUMER_TO_DEPENDENCY",
            "affected_semantics": "DEPENDENT_CANDIDATES_NOT_CONFIRMED_IMPACT",
            "provenance": "TWIN_DB_TOPOLOGY_READ_ONLY", "runtime_impact_state": "UNKNOWN",
            "runtime_authenticated": False, "tenant_acl_qualified": False,
            "redundancy_evaluated": False, "live_remediation_authorized": False,
            "affected": [{"node_id": n, "depth": i} for i, n in enumerate(chain)],
            "shortest_path_edges": [dict(zip(("edge_id", "source_id", "target_id", "relation_type"), e)) for e in probe.EXPECTED]}


class TwinProbeTests(TestCase):
    def test_seeded_path_is_topology_only(self):
        result = probe.qualify(payload())
        self.assertEqual(result["result"], "SOURCE_VERIFIED_TWIN_DB_TOPOLOGY_ONLY")
        self.assertEqual(result["path_edge_ids"], ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02", "ACME-E01"])
        self.assertEqual(result["observed_payments_impact"], "UNKNOWN")
        self.assertIsNone(result["run_id"])

    def test_missing_edge_rejected(self):
        p = payload(); p["shortest_path_edges"].pop()
        self.assertEqual(probe.qualify(p)["result"], "UNKNOWN")

    def test_fabricated_shortcut_rejected(self):
        p = payload(); p["shortest_path_edges"][1]["target_id"] = probe.ROOT
        self.assertEqual(probe.qualify(p)["result"], "UNKNOWN")

    def test_reversed_edge_rejected(self):
        p = payload(); p["shortest_path_edges"][0]["source_id"] = probe.ROOT
        self.assertEqual(probe.qualify(p)["result"], "UNKNOWN")

    def test_wrong_depth_rejected(self):
        p = payload(); p["affected"][-2]["depth"] = 2
        self.assertEqual(probe.qualify(p)["result"], "UNKNOWN")

    def test_boolean_depth_rejected(self):
        p = payload(); p["affected"][-1]["depth"] = True
        self.assertEqual(probe.qualify(p)["result"], "UNKNOWN")

    def test_unattested_claim_rejected(self):
        for key, value in (("runtime_authenticated", True), ("tenant_acl_qualified", True),
                           ("runtime_impact_state", "IMPACTED"), ("redundancy_evaluated", True)):
            p = payload(); p[key] = value
            with self.subTest(key=key): self.assertEqual(probe.qualify(p)["result"], "UNKNOWN")

    def test_no_token_makes_no_request(self):
        with mock.patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "", "AIOPS_ADMIN_TOKEN": ""}), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(probe.main(["--twin-url", "http://127.0.0.1:820"], lambda *a: self.fail("unexpected call")), 2)
        self.assertEqual(json.loads(out.getvalue())["reason"], "TOKEN_NOT_CONFIGURED")

    def test_bearer_only_in_request_not_json(self):
        with mock.patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "very-secret"}), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(probe.main(["--twin-url", "https://twin.example"], lambda base, token: payload() if token == "very-secret" else None), 0)
        self.assertNotIn("very-secret", out.getvalue())
        self.assertNotIn("https://twin.example", out.getvalue())

    def test_unauthorized_is_unknown(self):
        def fail(*args): raise HTTPError("https://twin.example", 401, "unauthorized", {}, None)
        with mock.patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "very-secret"}), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(probe.main(["--twin-url", "https://twin.example"], fail), 2)
        self.assertEqual(json.loads(out.getvalue())["reason"], "TWIN_AUTH_READ_FAILED")

    def test_redirect_does_not_forward_twin_bearer(self):
        self.assertIsNone(probe._RejectRedirects().redirect_request(
            None, None, 307, "Temporary Redirect", {}, "https://other.example"))

    def test_remote_http_refused(self):
        with self.assertRaises(SystemExit) as ctx:
            probe.main(["--twin-url", "http://twin.example"], lambda *a: self.fail("unexpected call"))
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    main()
