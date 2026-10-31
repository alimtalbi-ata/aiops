import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "debian_readonly_reporter",
    Path(__file__).resolve().parents[1] / "scripts" / "debian-readonly-reporter.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DebianReadonlyReporterTests(unittest.TestCase):
    def test_fixed_command_never_uses_shell(self):
        with mock.patch.object(MODULE.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            result = MODULE.fixed_command(["uptime", "-p"])
        self.assertTrue(result["available"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_collect_contains_only_allowlisted_probe_families(self):
        with mock.patch.object(MODULE, "fixed_command", return_value={
            "available": True, "returncode": 0, "stdout": "up", "stderr": ""
        }), mock.patch.object(MODULE, "docker_inventory", return_value={
            "available": True, "containers": [], "truncated": False
        }), mock.patch.object(MODULE, "tcp_probe", return_value={"reachable": False}):
            report = MODULE.collect()
        self.assertEqual(report["schema_version"], 3)
        self.assertEqual(set(report["tcp_loopback"]), {"5432", "7233", "17777", "3000", "9090"})
        self.assertNotIn("environment", report)
        self.assertNotIn("logs", report)
        self.assertNotIn("credentials", report)


    def test_docker_inventory_captures_topology_without_mounts_or_env(self):
        responses = [
            {"available": True, "returncode": 0, "stdout": "portal\n", "stderr": ""},
            {"available": True, "returncode": 0,
             "stdout": "running|healthy|portal:test|compose-demo|portal|2|0|net-public,net-data,|777/tcp=10.0.0.2:17777,;", "stderr": ""},
            {"available": True, "returncode": 0, "stdout": "net-public|bridge|local\nnet-data|bridge|local", "stderr": ""},
            {"available": True, "returncode": 0, "stdout": "portal|1.25%|200MiB / 1GiB|19.5%", "stderr": ""},
        ]
        with mock.patch.object(MODULE, "fixed_command", side_effect=responses):
            report = MODULE.docker_inventory()
        self.assertEqual(report["containers"][0]["networks"], ["net-public", "net-data"])
        self.assertEqual(report["containers"][0]["published_ports"][0]["host_port"], "17777")
        self.assertEqual(report["containers"][0]["compose_project"], "compose-demo")
        self.assertEqual(report["containers"][0]["restart_count"], 2)
        self.assertEqual(len(report["networks"]), 2)
        self.assertEqual(report["resource_usage"][0]["cpu_percent"], "1.25%")
        self.assertNotIn("mounts", report["containers"][0])
        self.assertNotIn("environment", report["containers"][0])

    def test_published_tcp_probes_follow_explicit_docker_bindings(self):
        docker = {"containers": [
            {"name": "portal", "published_ports": [
                {"host_ip": "10.79.94.202", "host_port": "17777"},
                {"host_ip": "0.0.0.0", "host_port": "3000"},
                {"host_ip": "10.79.94.202", "host_port": "17777"},
                {"host_ip": "10.79.94.202", "host_port": "5432"},
                {"host_ip": "not-an-ip", "host_port": "8080"},
            ]},
        ]}
        with mock.patch.object(MODULE, "tcp_probe", side_effect=[
            {"reachable": True}, {"reachable": False}
        ]) as probe:
            result = MODULE.published_tcp_probes(docker)
        self.assertEqual(result, [
            {"service": "grafana", "host": "127.0.0.1", "port": 3000, "reachable": False},
            {"service": "portal", "host": "10.79.94.202", "port": 17777, "reachable": True},
        ])
        self.assertEqual(probe.call_args_list, [
            mock.call(17777, "10.79.94.202"),
            mock.call(3000, "127.0.0.1"),
        ])

    def test_published_tcp_probes_ignore_unknown_ports_and_invalid_addresses(self):
        result = MODULE.published_tcp_probes({"containers": [
            {"published_ports": [
                {"host_ip": "10.79.94.202", "host_port": "7233"},
                {"host_ip": "invalid", "host_port": "8081"},
            ]}
        ]})
        self.assertEqual(result, [])


    def test_token_permissions_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / "token"
            token.write_text("ghp-not-a-real-token")
            token.chmod(0o644)
            with mock.patch.object(MODULE, "TOKEN_PATH", token):
                with self.assertRaisesRegex(RuntimeError, "permissions 0600"):
                    MODULE.publish({"schema_version": 1})

    def test_report_size_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_state, old_lock, old_latest = MODULE.STATE_DIR, MODULE.LOCK_PATH, MODULE.LATEST_PATH
            MODULE.STATE_DIR = Path(tmp)
            MODULE.LOCK_PATH = Path(tmp) / "lock"
            MODULE.LATEST_PATH = Path(tmp) / "latest.json"
            try:
                report = {"payload": "x" * (MODULE.MAX_REPORT_BYTES + 1)}
                with mock.patch.object(MODULE, "collect", return_value=report):
                    with self.assertRaisesRegex(RuntimeError, "size limit"):
                        MODULE.main()
            finally:
                MODULE.STATE_DIR, MODULE.LOCK_PATH, MODULE.LATEST_PATH = old_state, old_lock, old_latest


if __name__ == "__main__":
    unittest.main()
