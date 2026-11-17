"""Contract tests for the read-only existing-host reporter fragment."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/debian-runtime-readonly-probe.py"
spec = importlib.util.spec_from_file_location("debian_runtime_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class DebianRuntimeProbeTests(unittest.TestCase):
    def test_redaction_and_exact_ports(self):
        secret = "TEST_ONLY_PRIVATE_TOKEN_MUST_NOT_LEAK"
        image = "sha256:" + "a" * 64
        calls = []
        def runner(argv):
            calls.append(argv)
            if argv[:2] == ["docker", "inspect"]:
                return json.dumps({
                    "Image": image,
                    "State": {"Status": "running",
                              "Health": {"Status": "healthy"}},
                    "Config": {"Env": ["PASSWORD=" + secret],
                               "Labels": {"com.docker.compose.project": "aiops2-rebuild"}},
                    "HostConfig": {"PortBindings": {
                        "777/tcp": [{"HostIp": "0.0.0.0", "HostPort": "7777"}],
                        "17777/tcp": [{"HostIp": "127.0.0.1", "HostPort": "17777"}]}},
                    "Mounts": [{"Name": secret, "Source": "/private/" + secret}],
                    "NetworkSettings": {"Networks": {"private-" + secret: {}}},
                })
            if argv[:3] == ["docker", "image", "inspect"]:
                return json.dumps(["private.registry/image@sha256:" + "b" * 64])
            if argv[0] == "git":
                return "c" * 40 + "\n"
            return None
        fixed = dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc)
        import os
        old = os.environ.get("AIOPS_DEV_CHECKOUT")
        os.environ["AIOPS_DEV_CHECKOUT"] = "/synthetic/checkout"
        try:
            report = probe.collect(
                runner=runner,
                http_probe=lambda: {"http_status": 200, "qualified": True},
                tcp_probe=lambda port: port == "7777",
                clock=lambda: fixed)
        finally:
            if old is None:
                os.environ.pop("AIOPS_DEV_CHECKOUT", None)
            else:
                os.environ["AIOPS_DEV_CHECKOUT"] = old
        encoded = json.dumps(report, sort_keys=True)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("private.registry", encoded)
        self.assertEqual(report["checkout_sha"], "c" * 40)
        self.assertEqual(report["portal"]["compose_project"], "aiops2-rebuild")
        self.assertEqual(report["portal"]["bindings"][0]["host_port"], 7777)
        self.assertEqual(report["portal"]["bindings"][1]["host_port"], 17777)
        self.assertEqual(report["portal"]["image_id_sha256"], image)
        self.assertEqual(report["portal"]["registry_manifest_digests"],
                         ["sha256:" + "b" * 64])
        self.assertEqual(report["portal"]["mount_count"], 1)
        self.assertEqual(report["portal"]["network_count"], 1)
        self.assertEqual(report["tcp_loopback"],
                         {"7777": True, "17777": False, "17778": False})
        self.assertFalse(report["deployed_candidate_sha_verified"])
        self.assertFalse(report["single_portal_verified"])
        self.assertEqual(report["release_stable"], "NO_GO")
        self.assertTrue(all(cmd[0] in ("docker", "git") for cmd in calls))
        self.assertFalse(any("stop" in cmd or "run" in cmd or "rm" in cmd
                             for cmd in calls))

    def test_missing_inspect_and_invalid_health_fail_closed(self):
        result = probe.collect(
            runner=lambda argv: None,
            http_probe=lambda: {"http_status": None, "qualified": False},
            tcp_probe=lambda port: False,
            clock=lambda: dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc))
        self.assertFalse(result["portal"]["observed"])
        self.assertIsNone(result["checkout_sha"])
        self.assertFalse(result["http_7777"]["qualified"])
        self.assertEqual(result["release_stable"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
