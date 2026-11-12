"""Tests: existing reporter v1 must never fabricate immutable provenance."""
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "adapt_existing_debian_report.py"
spec = importlib.util.spec_from_file_location("adapt_existing_debian_report", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def report():
    return {"schema_version": 1, "collected_at": "2026-11-08T11:18:01Z",
            "host": {"reported_name": "SRV-DEB-05"},
            "docker": {"available": True, "truncated": False, "containers": [
                {"name": "worker", "image": "worker:latest", "state": "running",
                 "health": "healthy", "inspect_ok": True}]}}


class AdapterTests(unittest.TestCase):
    def test_preserves_only_known_metadata(self):
        x = m.adapt(report())
        c = x["containers"][0]
        self.assertIsNone(c["image_id"])
        self.assertEqual(c["configured_image"], "worker:latest")
        self.assertEqual(c["compose"], {})
        self.assertEqual(x["images"], [])
        self.assertIn("no_immutable_provenance", x["scope"])

    def test_truncated_is_error(self):
        x = report()
        x["docker"]["truncated"] = True
        self.assertIn("legacy_container_list_truncated", m.adapt(x)["errors"])

    def test_unavailable_is_error(self):
        x = report()
        x["docker"]["available"] = False
        self.assertIn("legacy_docker_unavailable", m.adapt(x)["errors"])

    def test_failed_inspect_is_error(self):
        x = report()
        x["docker"]["containers"][0]["inspect_ok"] = False
        self.assertIn("legacy_inspect_failed:worker", m.adapt(x)["errors"])

    def test_duplicate_names_refused(self):
        x = report()
        x["docker"]["containers"].append(dict(x["docker"]["containers"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            m.adapt(x)

    def test_bad_schema_refused(self):
        x = report()
        x["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema_version"):
            m.adapt(x)


if __name__ == "__main__":
    unittest.main()
