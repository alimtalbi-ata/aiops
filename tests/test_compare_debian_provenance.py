"""Regression tests for the conservative offline Debian provenance diff."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "compare_debian_provenance.py"
spec = importlib.util.spec_from_file_location("compare_debian_provenance", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def snapshot(containers=None, files=None, errors=None):
    return {"schema": "aiops2-debian-provenance-v1",
            "captured_at_utc": "2026-11-08T10:00:00+00:00",
            "containers": containers or [], "compose_files": files or [],
            "errors": errors or []}


def container(name, image, project="aiops2-rebuild"):
    return {"name": name, "image_id": image, "configured_image": "worker:stable",
            "compose": {"com.docker.compose.project": project,
                        "com.docker.compose.service": "worker",
                        "com.docker.compose.config-hash": "a"}}


class CompareTests(unittest.TestCase):
    def test_unchanged_never_authorizes_release(self):
        result = mod.compare(snapshot([container("worker", "sha256:1")]),
                             snapshot([container("worker", "sha256:1")]))
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["release_decision"], "HOLD")
        self.assertEqual(result["feature_parity"], "UNKNOWN")
        self.assertEqual(result["backup_restoration"], "NOT_ATTESTED")

    def test_image_drift_detected(self):
        result = mod.compare(snapshot([container("worker", "sha256:1")]),
                             snapshot([container("worker", "sha256:2")]))
        self.assertEqual(result["changes"][0]["kind"], "IDENTITY_CHANGED")
        self.assertEqual(result["changes"][0]["old_identity"]["image_id"], "sha256:1")

    def test_compose_project_drift_even_if_image_unchanged(self):
        result = mod.compare(snapshot([container("worker", "sha256:1")]),
                             snapshot([container("worker", "sha256:1", "aiops2-metrics-cutover")]))
        self.assertEqual(result["changes"][0]["kind"], "IDENTITY_CHANGED")

    def test_add_missing_and_compose_hash(self):
        before = snapshot([container("old", "sha256:1")],
                          [{"path": "/tmp/compose.yaml", "sha256": "a"}])
        after = snapshot([container("new", "sha256:2")],
                         [{"path": "/tmp/compose.yaml", "sha256": "b"}])
        result = mod.compare(before, after)
        self.assertEqual([x["kind"] for x in result["changes"]], ["ADDED", "MISSING"])
        self.assertEqual(result["compose_changes"][0]["new_sha256"], "b")

    def test_snapshot_errors_retained_and_no_promotion(self):
        result = mod.compare(snapshot(errors=["docker_ps:command_failed:1"]), snapshot())
        self.assertEqual(result["snapshot_errors"], ["docker_ps:command_failed:1"])
        self.assertEqual(result["release_decision"], "HOLD")

    def test_duplicate_container_names_refused(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mod.compare(snapshot([container("same", "sha256:1"),
                                  container("same", "sha256:2")]), snapshot())

    def test_invalid_schema_refused(self):
        with self.assertRaisesRegex(ValueError, "schema"):
            mod.compare({"schema": "untrusted"}, snapshot())


if __name__ == "__main__":
    unittest.main()
