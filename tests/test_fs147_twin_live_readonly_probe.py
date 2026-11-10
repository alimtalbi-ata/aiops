"""Offline regression for the real Twin GET-only qualification collector."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts" / "fs"))
from fs147_twin_live_readonly_probe import qualify_live, fetch_json
from fs147_twin_partition_gate import IsolationError


def fixtures():
    def node(identifier, namespace):
        return {"node_id": identifier, "namespace": namespace}
    def fact(identifier, node_id, run):
        return {"fact_id": identifier, "node_id": node_id,
                "value": {"run_id": run, "synthetic": True, "target_node_id": node_id}}
    return {
        "/api/twin/graph": {
            "nodes": [node("FS-NODE", "lab-fs147"), node("SAN-NODE", "san")],
            "edges": [{"edge_id": "FS-EDGE", "source_id": "FS-NODE",
                       "target_id": "FS-NODE", "relation_type": "depends_on"}]},
        "/api/twin/scenario/RUN-FS/facts": {
            "run_id": "RUN-FS", "synthetic": True, "facts": [fact("FACT-FS", "FS-NODE", "RUN-FS")]},
        "/api/twin/scenario/RUN-SAN/facts": {
            "run_id": "RUN-SAN", "synthetic": True, "facts": [fact("FACT-SAN", "SAN-NODE", "RUN-SAN")]},
    }


class LiveProbeContract(unittest.TestCase):
    def run_probe(self, captures):
        calls = []
        def fetch(base, path, token):
            calls.append(path)
            return captures[path]
        result = qualify_live("http://isolated-candidate", "read-only-token",
                              "lab-fs147", "san", "RUN-FS", "RUN-SAN", fetch=fetch)
        self.assertEqual(calls, ["/api/twin/graph",
                                 "/api/twin/scenario/RUN-FS/facts",
                                 "/api/twin/scenario/RUN-SAN/facts"])
        return result

    def test_real_api_capture_contract_passes_only_with_explicit_partitions(self):
        result = self.run_probe(fixtures())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["qualification"], "API_CAPTURE_ONLY_NOT_DEBIAN_E2E")


    def test_redirect_is_rejected_before_bearer_token_can_be_forwarded(self):
        from fs147_twin_live_readonly_probe import _RejectRedirects
        handler = _RejectRedirects()
        self.assertIsNone(handler.redirect_request(None, None, 302, "redirect", {},
                                                   "https://untrusted.example/collect"))
        with patch("fs147_twin_live_readonly_probe.build_opener") as builder:
            builder.return_value.open.side_effect = HTTPError(
                "http://isolated-candidate/api/twin/graph", 302,
                "redirect refused", {}, None)
            with self.assertRaisesRegex(IsolationError, "HTTPError"):
                fetch_json("http://isolated-candidate", "/api/twin/graph", "secret")
            self.assertIsInstance(builder.call_args.args[0], _RejectRedirects)
            self.assertEqual(builder.return_value.open.call_count, 1)

    def test_current_graph_without_namespace_must_hold(self):
        data = fixtures()
        for node in data["/api/twin/graph"]["nodes"]:
            del node["namespace"]
        with self.assertRaisesRegex(IsolationError, "unscoped"):
            self.run_probe(data)

    def test_san_fact_substitution_must_hold(self):
        data = fixtures()
        data["/api/twin/scenario/RUN-FS/facts"]["facts"][0]["node_id"] = "SAN-NODE"
        with self.assertRaisesRegex(IsolationError, "cross-namespace"):
            self.run_probe(data)

    def test_conflicting_scenario_namespace_must_hold(self):
        data = fixtures()
        data["/api/twin/scenario/RUN-FS/facts"]["namespace"] = "san"
        with self.assertRaisesRegex(IsolationError, "cross-namespace scenario provenance"):
            self.run_probe(data)

    def test_conflicting_fact_namespace_must_hold(self):
        data = fixtures()
        data["/api/twin/scenario/RUN-SAN/facts"]["facts"][0]["namespace"] = "lab-fs147"
        with self.assertRaisesRegex(IsolationError, "cross-namespace fact provenance"):
            self.run_probe(data)

    def test_cross_namespace_dependency_must_hold(self):
        data = fixtures()
        data["/api/twin/graph"]["edges"][0]["target_id"] = "SAN-NODE"
        with self.assertRaisesRegex(IsolationError, "cross-namespace"):
            self.run_probe(data)

    def test_run_mismatch_must_hold(self):
        data = fixtures()
        data["/api/twin/scenario/RUN-FS/facts"]["run_id"] = "RUN-SAN"
        with self.assertRaisesRegex(IsolationError, "expected Core RUN"):
            self.run_probe(data)

    def test_same_run_rejected_without_http_calls(self):
        calls = []
        with self.assertRaisesRegex(IsolationError, "distinct"):
            qualify_live("http://isolated", "token", "lab-fs147", "san",
                         "RUN-FS", "RUN-FS",
                         fetch=lambda *args: calls.append(args))
        self.assertFalse(calls)

    def test_unsafe_run_rejected_without_http_calls(self):
        calls = []
        with self.assertRaisesRegex(IsolationError, "unsafe"):
            qualify_live("http://isolated", "token", "lab-fs147", "san",
                         "RUN/FS", "RUN-SAN",
                         fetch=lambda *args: calls.append(args))
        self.assertFalse(calls)


    def test_ambiguous_base_urls_rejected_without_http_request(self):
        # A query or fragment can silently alter the requested API path.
        # Credentialed captures must use a canonical origin, not a URL suffix.
        for base in ("http://isolated-candidate?next=/api/twin/graph",
                     "http://isolated-candidate/#shadow",
                     "http://isolated-candidate/other",
                     "http://isolated-candidate@external.example",
                     "http://isolated-candidate/\\n"):
            with self.subTest(base=base), patch(
                    "fs147_twin_live_readonly_probe.build_opener") as builder:
                with self.assertRaisesRegex(IsolationError, "invalid Twin API base URL"):
                    fetch_json(base, "/api/twin/graph", "secret")
                builder.assert_not_called()

    def test_canonical_origin_accepts_get_only(self):
        from email.message import Message
        from unittest.mock import MagicMock
        import json
        response = MagicMock()
        response.status = 200
        response.headers.get_content_type.return_value = "application/json"
        response.read.return_value = json.dumps({"nodes": [], "edges": []}).encode()
        response.__enter__.return_value = response
        with patch("fs147_twin_live_readonly_probe.build_opener") as builder:
            builder.return_value.open.return_value = response
            result = fetch_json("http://isolated-candidate/", "/api/twin/graph", "secret")
            self.assertEqual(result, {"nodes": [], "edges": []})
            request = builder.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, "http://isolated-candidate/api/twin/graph")

if __name__ == "__main__":
    unittest.main()
