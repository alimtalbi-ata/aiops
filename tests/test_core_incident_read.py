"""Unit contract for Core incident list; no PostgreSQL instance is claimed."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from core import incident_read

class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, sql):
        self.sql = sql
        return self
    def fetchall(self):
        return self.rows

class CoreIncidentReadTests(unittest.TestCase):
    def test_bounded_read_only_query_and_projection(self):
        cursor = FakeCursor([("INC-1", "EXT-1", "SAN failure", "P1", "OPEN",
                              "ACME-PAYMENTS", "2026-10-27T21:00:00Z", "thruk", False)])
        with patch.object(incident_read, "db", return_value=cursor):
            result = incident_read.list_incidents()
        self.assertEqual(result["items"][0]["incident_id"], "INC-1")
        self.assertFalse(result["items"][0]["synthetic"])
        self.assertIn("limit 50", cursor.sql.lower())
        self.assertTrue(cursor.sql.strip().lower().startswith("select "))
        self.assertNotIn("payload", cursor.sql.lower())

    def test_empty_inventory_is_not_synthetic(self):
        with patch.object(incident_read, "db", return_value=FakeCursor([])):
            self.assertEqual(incident_read.list_incidents(), {"items": []})

    def test_database_failure_not_silently_converted_to_empty(self):
        with patch.object(incident_read, "db", side_effect=ConnectionError("database unavailable")):
            with self.assertRaises(ConnectionError):
                incident_read.list_incidents()

if __name__ == "__main__":
    unittest.main()
