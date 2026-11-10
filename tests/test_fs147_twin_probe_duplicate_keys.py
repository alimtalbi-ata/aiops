"""Regression: fail closed on ambiguous Twin HTTP evidence, without runtime access."""
import io
import sys
import unittest
from pathlib import Path
from email.message import Message

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "fs"))
from fs147_twin_live_readonly_probe import fetch_json
from fs147_twin_partition_gate import IsolationError


class Response:
    status = 200
    headers = Message()

    def __init__(self, body):
        self.body = io.BytesIO(body)
        self.headers["Content-Type"] = "application/json"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()

    def read(self, n):
        return self.body.read(n)


class DuplicateJsonEvidenceTests(unittest.TestCase):
    def capture(self, body):
        return fetch_json("https://twin.example", "/api/twin/graph", "fake-test-token",
                          opener=lambda request, timeout: Response(body.encode("utf-8")))

    def test_valid_unique_keys(self):
        self.assertEqual(self.capture('{"nodes":[{"node_id":"fs1","namespace":"lab"}],"edges":[]}')["nodes"][0]["namespace"], "lab")

    def test_duplicate_namespace_rejected(self):
        with self.assertRaises(IsolationError):
            self.capture('{"nodes":[{"node_id":"fs1","namespace":"lab","namespace":"san"}],"edges":[]}')

    def test_duplicate_run_id_in_nested_fact_rejected(self):
        with self.assertRaises(IsolationError):
            self.capture('{"run_id":"fs","facts":[{"value":{"run_id":"fs","run_id":"san"}}]}')

    def test_duplicate_top_level_graph_rejected(self):
        with self.assertRaises(IsolationError):
            self.capture('{"nodes":[],"nodes":[{"node_id":"san1"}],"edges":[]}')

    def test_invalid_json_rejected(self):
        with self.assertRaises(IsolationError):
            self.capture('{"nodes":')


if __name__ == "__main__":
    unittest.main()
