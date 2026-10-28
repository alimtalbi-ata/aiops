"""Real Twin HTTP container + PostgreSQL 16 seed integration, never a LIVE proof.

Only runs in quality.yml with ephemeral services and CI-only credentials.
No mocks, no production network, no mutation of the seeded topology.
"""
import os
import unittest

import psycopg
import requests

BASE = os.environ["AIOPS_TWIN_CI_URL"]
TOKEN = os.environ["AIOPS_TWIN_CI_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]


class TwinImpactRealIntegration(unittest.TestCase):
    def read(self, node_id, token=TOKEN):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        return requests.get(
            BASE + "/api/twin/impact/" + node_id,
            headers=headers, timeout=5, allow_redirects=False,
        )

    def test_ephemeral_seed_is_25_nodes_and_23_directed_edges(self):
        with psycopg.connect(DATABASE_URL) as c:
            self.assertEqual(c.execute("select count(*) from aiops.twin_nodes").fetchone()[0], 25)
            self.assertEqual(c.execute("select count(*) from aiops.twin_edges").fetchone()[0], 23)
            self.assertEqual(
                c.execute(
                    "select source_id,target_id from aiops.twin_edges "
                    "where edge_id='ACME-E08'"
                ).fetchone(),
                ("ACME-STO-PURE01", "ACME-SAN-FABRIC-A"),
            )

    def test_san_fabric_a_reaches_only_real_dependent_consumers(self):
        response = self.read("ACME-SAN-FABRIC-A")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        data = response.json()
        expected = {
            "ACME-SAN-FABRIC-A": 0,
            "ACME-STO-PURE01": 1,
            "ACME-STO-POWERMAX01": 1,
            "ACME-VM-PAY01": 2,
            "ACME-VM-PAY02": 2,
            "ACME-APP-ERP": 2,
            "ACME-APP-ORACLEPAY": 3,
            "ACME-SVC-ERP": 3,
            "ACME-SVC-PAYMENTS": 4,
            "ACME-BIZ-PAYMENTS": 5,
        }
        self.assertEqual(
            {item["node_id"]: item["depth"] for item in data["affected"]},
            expected,
        )
        # Every path edge is a real row in the seeded PostgreSQL graph.
        # No synthetic SAN -> host shortcut may be emitted.
        edges = data["shortest_path_edges"]
        self.assertEqual(
            [edge["edge_id"] for edge in edges],
            ["ACME-E01", "ACME-E02", "ACME-E04", "ACME-E05",
             "ACME-E06", "ACME-E07", "ACME-E08", "ACME-E14",
             "ACME-E15", "ACME-E16"],
        )
        self.assertEqual(
            data["path_semantics"],
            "SEEDED_TOPOLOGY_SHORTEST_HOPS_NOT_RUNTIME_CAUSALITY",
        )
        with psycopg.connect(DATABASE_URL) as c:
            actual = {
                row[0]: row[1:]
                for row in c.execute(
                    "select edge_id,source_id,target_id,relation_type "
                    "from aiops.twin_edges"
                ).fetchall()
            }
        for edge in edges:
            with self.subTest(edge=edge["edge_id"]):
                self.assertEqual(
                    (edge["source_id"], edge["target_id"], edge["relation_type"]),
                    actual[edge["edge_id"]],
                )
                self.assertEqual(
                    expected[edge["source_id"]],
                    expected[edge["target_id"]] + 1,
                )
        self.assertNotIn("ACME-E10", {e["edge_id"] for e in edges})
        self.assertNotIn("ACME-E09", {e["edge_id"] for e in edges})
        self.assertEqual(data["traversal_direction"], "REVERSE_CONSUMER_TO_DEPENDENCY")
        self.assertEqual(data["affected_semantics"], "DEPENDENT_CANDIDATES_NOT_CONFIRMED_IMPACT")
        self.assertEqual(data["runtime_impact_state"], "UNKNOWN")
        self.assertIs(data["runtime_authenticated"], False)
        self.assertIs(data["tenant_acl_qualified"], False)
        self.assertIs(data["redundancy_evaluated"], False)
        self.assertIs(data["live_remediation_authorized"], False)
        # SAN-B is a sibling path, while RHEL01 is a VM dependency, not a SAN consumer.
        returned = {item["node_id"] for item in data["affected"]}
        self.assertNotIn("ACME-SAN-FABRIC-B", returned)
        self.assertNotIn("ACME-SRV-RHEL01", returned)
        self.assertNotIn("ACME-APP-PORTAL", returned)
        self.assertEqual(response.json(), self.read("ACME-SAN-FABRIC-A").json())

    def test_direction_is_not_inverted_or_invented(self):
        # Business node depends on the service; it has no dependent consumers.
        r = self.read("ACME-BIZ-PAYMENTS")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(
            [(item["node_id"], item["depth"]) for item in r.json()["affected"]],
            [("ACME-BIZ-PAYMENTS", 0)],
        )
        self.assertEqual(r.json()["shortest_path_edges"], [])

    def test_unknown_node_and_missing_auth_fail_closed(self):
        for token in (None, "", "incorrect", TOKEN + "-extra"):
            with self.subTest(token=token):
                r = self.read("ACME-SAN-FABRIC-A", token)
                self.assertEqual(r.status_code, 401, r.text)
                self.assertEqual(r.headers.get("cache-control"), "no-store")
                self.assertNotIn("ACME-STO-PURE01", r.text)
                self.assertNotIn("shortest_path_edges", r.text)
        r = self.read("ACME-NODE-NOT-SEEDED")
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.headers.get("cache-control"), "no-store")
        self.assertNotIn("ACME-SVC-PAYMENTS", r.text)


if __name__ == "__main__":
    unittest.main()
