"""Disposable no-host regression for safe poller."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/debian-poller-qualification.py"
spec = importlib.util.spec_from_file_location("poller", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PollerContract(unittest.TestCase):
    def test_safe_installer(self):
        script = ROOT / "deploy/deploy-demo-studio-v2.sh"
        src = script.read_text()
        self.assertEqual(subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode, 0)
        self.assertIn("debian-portal-preflight.py", src)
        self.assertIn("debian-poller-qualification.py", (ROOT / "deploy/debian-portal-preflight.py").read_text())
        for bad in ("docker stop", "docker run", "docker rename", "docker rm", "docker compose up"):
            self.assertNotIn(bad, src)

    def test_redacted_probe(self):
        secret = "SYNTHETIC_SECRET_NEVER_EXPORT"
        image = "sha256:" + "a"*64
        def runner(argv, timeout=12):
            if argv[:3] == ["docker", "inspect", "--type"]:
                return json.dumps([{"Id": "b"*64, "Image": image,
                    "State": {"Status": "running", "Health": {"Status": "healthy"}},
                    "Config": {"Env": ["TOKEN=" + secret],
                               "Labels": {"com.docker.compose.project": "aiops2-rebuild", "secret": secret}},
                    "HostConfig": {"PortBindings": {"777/tcp": [{"HostPort": "7777", "HostIp": "0.0.0.0"}]}},
                    "Mounts": [{"Source": secret}],
                    "NetworkSettings": {"Networks": {secret: {}}}}])
            if argv[:3] == ["docker", "image", "inspect"]:
                return json.dumps(["private/" + secret + "@sha256:" + "c"*64])
            if argv[0] == "git":
                return "d"*40
            return None
        r = mod.collect(runner=runner, http_probe=lambda: {"status": 200, "qualified": True},
                        tcp_probe=lambda port: port == 7777)
        self.assertNotIn(secret, json.dumps(r))
        self.assertEqual(r["portal"]["image_id"], image)
        self.assertEqual(r["portal"]["container_id"], "b"*64)
        self.assertEqual(r["portal"]["manifest_digests"], ["sha256:" + "c"*64])
        self.assertEqual(r["host_portal_7777"], "PASS")
        self.assertEqual(r["release_stable"], "NO_GO")

    def test_fail_closed(self):
        r = mod.collect(runner=lambda argv: None,
                        http_probe=lambda: {"status": None, "qualified": False},
                        tcp_probe=lambda port: False)
        self.assertEqual(r["host_portal_7777"], "FAIL_OR_UNKNOWN")
        self.assertEqual(r["portal"]["inspection"], "UNKNOWN")
        self.assertIsNone(r["stable_checkout_sha"])

    def test_one_shot_republish_only_fresh_whitelisted_report(self):
        now = dt.datetime(2026, 11, 2, 12, 29, tzinfo=dt.timezone.utc)
        report = {
            "agent": {"name": "aiops-debian-readonly", "version": "1.0.0"},
            "collected_at": "2026-11-02T12:28:01Z",
            "schema_version": 1,
            "docker": {"available": True, "truncated": False, "containers": [
                {"name": "aiops2-rebuild-portal", "image": "portal:synthetic",
                 "state": "running", "health": "healthy", "inspect_ok": True}]},
            "host": {"reported_name": "REDACTED"},
            "resources": {"memory_bytes": {"total": 12345}},
            "tcp_loopback": {"7777": True, "17777": False},
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "latest.json"
            p.write_text(json.dumps(report))
            output = mod.validated_fresh_local_report(p, now=now)
            self.assertIsNotNone(output)
            self.assertEqual(json.loads(output)["collected_at"], report["collected_at"])
            report["docker"]["containers"][0]["secret_token"] = "SYNTHETIC_NEVER_PUBLISH"
            p.write_text(json.dumps(report))
            self.assertIsNone(mod.validated_fresh_local_report(p, now=now))
            del report["docker"]["containers"][0]["secret_token"]
            report["collected_at"] = "2026-11-02T11:01:01Z"
            p.write_text(json.dumps(report))
            self.assertIsNone(mod.validated_fresh_local_report(p, now=now))
            report["collected_at"] = "2026-11-02T12:28:01Z"
            report["unexpected"] = "SYNTHETIC_NEVER_PUBLISH"
            p.write_text(json.dumps(report))
            self.assertIsNone(mod.validated_fresh_local_report(p, now=now))
            p.write_text("X" * 32769)
            self.assertIsNone(mod.validated_fresh_local_report(p, now=now))

    def test_no_docker_mutation_in_source(self):
        source = SCRIPT.read_text()
        for bad in ("docker stop", "docker run", "docker rm", "docker compose up", "shell=True", "os.system("):
            self.assertNotIn(bad, source)
        self.assertIn("publish.lock", source)
        self.assertIn("poller-qualification.json", source)


if __name__ == "__main__":
    unittest.main()
