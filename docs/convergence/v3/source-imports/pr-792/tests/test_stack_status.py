import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy"))
SPEC = importlib.util.spec_from_file_location("aiops_stack_status", ROOT / "deploy" / "status.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(service="aiops2-core", state="running", health="healthy"):
    return {
        "Name": "aiops2-rebuild-" + service.removeprefix("aiops2-"),
        "Service": service,
        "Project": "aiops2-rebuild",
        "State": state,
        "Health": health,
        "ExitCode": 0,
        "Command": "DO_NOT_EXPOSE confidential-password",
    }


def settings():
    return {
        "AIOPS_STACK_ID": "aiops2-rebuild",
        "AIOPS_PORTAL_HOST_PORT": "17777",
        "POSTGRES_PASSWORD": "never-print-secret",
    }


class StackReadOnlyStatusTests(unittest.TestCase):
    def test_parses_json_list_and_json_lines(self):
        one = fixture()
        self.assertEqual(MODULE.parse_compose_ps(json.dumps([one])), [one])
        self.assertEqual(MODULE.parse_compose_ps(json.dumps(one) + "\n"), [one])

    def test_health_report_excludes_docker_command_and_secret(self):
        data = json.dumps([fixture()])
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout=data, stderr="")

        report = MODULE.collect(settings(), execute=run, check_portal=False)
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["services"][0]["condition"], "PASS")
        self.assertTrue(report["secrets_in_report"] is False)
        serialized = json.dumps(report)
        self.assertNotIn("confidential-password", serialized)
        self.assertNotIn("never-print-secret", serialized)
        self.assertEqual(calls[0][:4], ["docker", "compose", "--env-file", ".env"])
        self.assertNotIn("down", calls[0])

    def test_temporal_bootstrap_completed_zero_is_expected(self):
        report = MODULE.classify_service(fixture("aiops2-temporal-schema", "exited", ""), "aiops2-rebuild")
        self.assertEqual(report["condition"], "PASS")

    def test_temporal_bootstrap_failed_is_not_ignored(self):
        bad = fixture("aiops2-temporal-schema", "exited", "")
        bad["ExitCode"] = 2
        report = MODULE.classify_service(bad, "aiops2-rebuild")
        self.assertEqual(report["condition"], "FAIL")

    def test_unhealthy_service_yields_fail(self):
        data = json.dumps([fixture(health="unhealthy")])
        report = MODULE.collect(
            settings(), execute=lambda *a, **k: SimpleNamespace(returncode=0, stdout=data),
            check_portal=False,
        )
        self.assertEqual(report["result"], "FAIL")
        self.assertIn("unhealthy_service:aiops2-core", report["issues"])

    def test_service_without_healthcheck_is_unverified(self):
        data = json.dumps([fixture(health="")])
        report = MODULE.collect(
            settings(), execute=lambda *a, **k: SimpleNamespace(returncode=0, stdout=data),
            check_portal=False,
        )
        self.assertEqual(report["result"], "UNKNOWN")

    def test_foreign_project_rejected(self):
        foreign = fixture()
        foreign["Project"] = "aiops2"
        with self.assertRaisesRegex(ValueError, "foreign_container"):
            MODULE.classify_service(foreign, "aiops2-rebuild")

    def test_docker_error_is_reported_without_stderr_details(self):
        response = SimpleNamespace(returncode=1, stdout="", stderr="secret-value")
        report = MODULE.collect(
            settings(), execute=lambda *a, **k: response,
            check_portal=False,
        )
        self.assertEqual(report["result"], "UNKNOWN")
        self.assertNotIn("secret-value", json.dumps(report))

    def test_portal_health_check_does_not_use_auth_token(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, count): return b'{"status":"ok"}'

        with patch.object(MODULE.urllib.request, "urlopen", return_value=Response()) as mocked:
            result = MODULE.portal_health(17777)
        self.assertEqual(result["status"], "PASS")
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:17777/health")
        self.assertNotIn("Authorization", request.headers)

    def test_cli_writes_single_redacted_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = pathlib.Path(tmp) / ".env"
            env.write_text("AIOPS_STACK_ID=aiops2-rebuild\nAIOPS_PORTAL_HOST_PORT=17777\nPOSTGRES_PASSWORD=secret-in-fixture\n")
            output = pathlib.Path(tmp) / "report.json"
            with patch.object(MODULE, "collect", return_value={"result":"PASS","issues":[],"secrets_in_report":False}):
                self.assertEqual(MODULE.main(["--env", str(env), "--report", str(output), "--no-health-http"]), 0)
            self.assertTrue(output.is_file())
            self.assertNotIn("secret-in-fixture", output.read_text())


if __name__ == "__main__":
    unittest.main()
