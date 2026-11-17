"""No-Docker regression contract for the existing-host read-only probe."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import debian_runtime_probe as probe


def sample(host_port="7777"):
    return json.dumps([{
        "Image": "sha256:" + "a" * 64,
        "Config": {"Env": ["SECRET_PASSWORD=do-not-publish", "TOKEN=hidden"],
                   "Labels": {"com.docker.compose.project": "aiops2-rebuild",
                              "com.docker.compose.service": "aiops2-portal",
                              "org.opencontainers.image.revision": "b" * 40,
                              "SECRET": "do-not-publish"}},
        "HostConfig": {"PortBindings": {"777/tcp": [
            {"HostIp": "0.0.0.0", "HostPort": host_port}]}},
        "NetworkSettings": {"Ports": {"777/tcp": [
            {"HostIp": "0.0.0.0", "HostPort": host_port}]},
            "Networks": {"aiops2-rebuild-public": {"IPAddress": "10.1.1.2"}}},
        "Mounts": [{"Type": "bind", "Source": "/secret/host/path",
                    "Destination": "/run/secrets"},
                   {"Type": "volume", "Name": "aiops2-data",
                    "Source": "/var/lib/docker/volumes/secret"}],
        "State": {"Status": "running", "Health": {"Status": "healthy"}}
    }])


class ReadOnlyReporterTests(unittest.TestCase):
    def test_redaction_and_verified_local_binding(self):
        seen = []
        def fake(argv, timeout=5):
            seen.append(argv)
            if argv[:2] == ["docker", "inspect"]:
                return sample() if argv[-1] == probe.PORTAL else None
            return None
        with patch.object(probe, "_run", side_effect=fake), \
             patch.object(probe, "_http_7777",
                          return_value={"http_200_json_ok": True}), \
             patch.object(probe, "_tcp", return_value={"reachable": True}), \
             patch.object(probe, "_sha_file", return_value=None):
            receipt = probe.collect_runtime_contract()
        self.assertEqual(receipt["local_7777"], "VERIFIED_BY_HOST_PROBE")
        self.assertEqual(receipt["portal"]["compose_project"], "aiops2-rebuild")
        self.assertEqual(receipt["portal"]["image_id_sha256"], "sha256:" + "a"*64)
        self.assertEqual(receipt["portal"]["named_volume_names"], ["aiops2-data"])
        self.assertEqual(receipt["portal"]["bind_mount_count"], 1)
        self.assertEqual(receipt["candidate"]["inspection"], "UNKNOWN")
        self.assertEqual(receipt["unique_public_entrypoint"], "NOT_VERIFIED")
        serialized = json.dumps(receipt)
        for forbidden in ("do-not-publish", "TOKEN=hidden", "/secret/host/path",
                          "/var/lib/docker", "10.1.1.2"):
            self.assertNotIn(forbidden, serialized)
        self.assertTrue(all(x[0] in ("docker", "git") for x in seen))
        self.assertFalse(any("stop" in x or "run" in x for x in seen))

    def test_wrong_port_and_http_failure_are_not_verified(self):
        with patch.object(probe, "_run", side_effect=lambda argv, timeout=5:
                          sample("17777") if argv[0] == "docker" else None), \
             patch.object(probe, "_http_7777",
                          return_value={"http_200_json_ok": True}), \
             patch.object(probe, "_tcp", return_value={"reachable": False}), \
             patch.object(probe, "_sha_file", return_value=None):
            self.assertEqual(probe.collect_runtime_contract()["local_7777"],
                             "NOT_VERIFIED")
        with patch.object(probe, "_run", side_effect=lambda argv, timeout=5:
                          sample() if argv[0] == "docker" else None), \
             patch.object(probe, "_http_7777",
                          return_value={"http_200_json_ok": False}), \
             patch.object(probe, "_tcp", return_value={"reachable": True}), \
             patch.object(probe, "_sha_file", return_value=None):
            self.assertEqual(probe.collect_runtime_contract()["local_7777"],
                             "NOT_VERIFIED")

    def test_malformed_bindings_fail_closed(self):
        self.assertEqual(probe._ports({"777/tcp": [
            {"HostIp": "0.0.0.0", "HostPort": "7777;echo secret"}]}), [])
        self.assertEqual(probe._ports({"not-port": [
            {"HostIp": "0.0.0.0", "HostPort": "7777"}]}), [])


if __name__ == "__main__":
    unittest.main()
