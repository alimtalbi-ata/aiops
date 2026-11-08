"""Offline regression tests for the review-only Debian provenance collector."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "debian_provenance_snapshot.py"
spec = importlib.util.spec_from_file_location("debian_provenance_snapshot", MODULE)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class ProvenanceTests(unittest.TestCase):
    def test_no_environment_or_secret_labels_or_log_data(self):
        container = {
            "Name": "/worker",
            "Id": "abc123",
            "Created": "2026-11-08T00:00:00Z",
            "Image": "sha256:abcdef",
            "Config": {
                "Image": "worker:test",
                "Env": ["TOKEN=never-publish"],
                "Labels": {
                    "com.docker.compose.project": "aiops2-rebuild",
                    "com.docker.compose.service": "worker",
                    "secret.label": "never-publish",
                },
            },
            "State": {"Status": "running", "Health": {"Status": "healthy"}},
            "Mounts": [{"Type": "volume", "Name": "worker_data",
                        "Source": "/var/lib/docker/volumes/worker_data/_data",
                        "Destination": "/data", "RW": True}],
            "NetworkSettings": {"Networks": {"aiops2": {"IPAddress": "172.0.0.2"}}},
        }
        image = {"Id": "sha256:abcdef", "Created": "2026-11-08T00:00:00Z",
                 "RepoTags": ["worker:test"], "RepoDigests": ["worker@sha256:xyz"],
                 "Config": {"Env": ["PASSWORD=never-publish"]}}
        def fake_run(*args, **kwargs):
            self.assertEqual(args[0], "docker")
            if args[1] == "ps":
                return "worker\n", None
            raise AssertionError("unexpected run")
        def fake_json(*args, **kwargs):
            if args[0] == "inspect":
                return [container], None
            if args[:2] == ("image", "inspect"):
                return [image], None
            raise AssertionError("unexpected docker_json")
        with mock.patch.object(snapshot, "run", side_effect=fake_run), \
             mock.patch.object(snapshot, "docker_json", side_effect=fake_json):
            data = snapshot.collect()
        encoded = json.dumps(data)
        self.assertNotIn("never-publish", encoded)
        self.assertNotIn("secret.label", encoded)
        self.assertNotIn("IPAddress", encoded)
        self.assertEqual(data["containers"][0]["compose"]["com.docker.compose.service"], "worker")
        self.assertEqual(data["images"][0]["repo_digests"], ["worker@sha256:xyz"])
        self.assertEqual(data["containers"][0]["mounts"][0]["name"], "worker_data")
        self.assertEqual(data["scope"], "read_only_current_state_not_deployment_history")

    def test_failure_is_reported_not_fabricated(self):
        with mock.patch.object(snapshot, "run", return_value=(None, "command_failed:1")):
            data = snapshot.collect()
        self.assertEqual(data["containers"], [])
        self.assertEqual(data["errors"], ["docker_ps:command_failed:1"])

    def test_compose_file_hash_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "compose.yaml"
            src.write_text("services: {}\n")
            link = Path(td) / "link.yaml"
            link.symlink_to(src)
            self.assertEqual(len(snapshot.sha256_file(src)), 64)
            self.assertIsNone(snapshot.sha256_file(link))
            self.assertIsNone(snapshot.sha256_file(Path(td) / ".env"))

    def test_optional_output_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "result.json"
            dest.write_text("preserve me")
            with mock.patch("sys.argv", ["snapshot", "--output", str(dest)]), \
                 mock.patch.object(snapshot, "collect", return_value={"errors": []}):
                with self.assertRaises(FileExistsError):
                    snapshot.main()
            self.assertEqual(dest.read_text(), "preserve me")

    def test_optional_output_private_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "result.json"
            with mock.patch("sys.argv", ["snapshot", "--output", str(dest)]), \
                 mock.patch.object(snapshot, "collect", return_value={"errors": []}), \
                 mock.patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(snapshot.main(), 0)
            self.assertEqual(os.stat(dest).st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(dest.read_text()), {"errors": []})


if __name__ == "__main__":
    unittest.main()
