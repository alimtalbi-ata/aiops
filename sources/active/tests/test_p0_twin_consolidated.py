import unittest
from unittest.mock import patch

from fastapi import HTTPException
from twin import main as twin


class TwinP0Tests(unittest.TestCase):

    def test_missing_token_denied(self):
        with patch.object(twin, "db") as database:
            with self.assertRaises(HTTPException) as caught:
                twin.impact("ACME-SAN-FABRIC-A", authorization=None)

            self.assertEqual(caught.exception.status_code, 401)
            database.assert_not_called()

    def test_invalid_token_denied(self):
        with patch.object(twin, "db") as database:
            with self.assertRaises(HTTPException) as caught:
                twin.impact(
                    "ACME-SAN-FABRIC-A",
                    authorization="Bearer invalid-token",
                )

            self.assertEqual(caught.exception.status_code, 401)
            database.assert_not_called()

    def test_internal_token_accepted(self):
        with patch.dict(
            twin.os.environ,
            {"AIOPS_INTERNAL_TOKEN": "test-internal-token"},
        ):
            twin.require_twin_read_auth(
                "Bearer test-internal-token"
            )

    def test_admin_token_accepted(self):
        twin.require_twin_read_auth(
            "Bearer " + twin.SIM_TOKEN
        )

    def test_malformed_bearer_denied(self):
        with self.assertRaises(HTTPException) as caught:
            twin.require_twin_read_auth("invalid-token")

        self.assertEqual(caught.exception.status_code, 401)

    def test_missing_node_returns_404(self):
        class FakeCursor:
            def execute(self, sql, params=None):
                self.sql = sql
                return self

            def fetchone(self):
                return None

        class FakeDB:
            def __enter__(self):
                return FakeCursor()

            def __exit__(self, *args):
                return False

        with patch.object(twin, "db", return_value=FakeDB()):
            with self.assertRaises(HTTPException) as caught:
                twin.impact(
                    "UNKNOWN-NODE",
                    authorization="Bearer " + twin.SIM_TOKEN,
                )

        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()


class TwinGraphP0Tests(unittest.TestCase):

    def test_reverse_impact_and_real_edges(self):
        import json

        class FakeCursor:
            def __init__(self):
                self.queries = []

            def execute(self, sql, params=None):
                self.queries.append((sql, params))
                return self

            def fetchone(self):
                return (1,)

            def fetchall(self):
                sql = self.queries[-1][0].lower()
                if "with recursive consumers" in sql:
                    return [
                        ("SAN", "STORAGE", "SAN", 5, 0),
                        ("VM", "VM", "VM", 4, 1),
                        ("SERVICE", "SERVICE", "SERVICE", 3, 2),
                    ]
                if "select edge_id, source_id" in sql:
                    return [
                        ("E1", "VM", "SAN", "DEPENDS_ON"),
                        ("E2", "SERVICE", "VM", "RUNS_ON"),
                        ("E3", "SERVICE", "SAN", "UNRELATED"),
                    ]
                raise AssertionError(f"SQL inattendu : {sql}")

        class FakeDB:
            def __init__(self):
                self.cursor = FakeCursor()

            def __enter__(self):
                return self.cursor

            def __exit__(self, *args):
                return False

        fake = FakeDB()

        with patch.object(twin, "db", return_value=fake):
            response = twin.impact(
                "SAN",
                authorization="Bearer " + twin.SIM_TOKEN,
            )

        data = json.loads(response.body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["node_id"] for item in data["affected"]],
            ["SAN", "VM", "SERVICE"],
        )
        self.assertEqual(
            [edge["edge_id"] for edge in data["shortest_path_edges"]],
            ["E1", "E2"],
        )
        self.assertEqual(data["max_depth"], 8)
        self.assertEqual(data["runtime_impact_state"], "UNKNOWN")
        self.assertFalse(data["live_remediation_authorized"])
        self.assertEqual(
            response.headers["cache-control"], "no-store"
        )

        queries = [sql.lower() for sql, _ in fake.cursor.queries]

        self.assertTrue(
            any("repeatable read read only" in sql for sql in queries)
        )
        self.assertTrue(
            any("join consumers c on e.target_id = c.id" in sql
                for sql in queries)
        )
        self.assertTrue(
            any("c.depth < 8" in sql for sql in queries)
        )
