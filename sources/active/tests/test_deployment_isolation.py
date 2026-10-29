import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aiops_isolation", ROOT / "deploy" / "plan_isolation.py")
ISOLATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ISOLATION)


def env_fixture():
    env = {
        "AIOPS_STACK_ID": "aiops2-rebuild",
        "COMPOSE_PROJECT_NAME": "aiops2-rebuild",
        "AIOPS_BIND_IP": "127.0.0.1",
        "AIOPS_PORTAL_HOST_PORT": "17777",
        "AIOPS_GLPI_HOST_PORT": "18080",
        "AIOPS_N8N_HOST_PORT": "15678",
        "AIOPS_PROMETHEUS_HOST_PORT": "19090",
        "AIOPS_GRAFANA_HOST_PORT": "13000",
        "AIOPS_ALERTMANAGER_HOST_PORT": "19093",
    }
    env["POSTGRES_PASSWORD"] = "private-unittest-value"
    return env


def compose_fixture():
    stack = "aiops2-rebuild"
    return {
        "name": stack,
        "services": {
            service: {
                "container_name": stack + "-" + service.removeprefix("aiops2-"),
                "networks": ["aiops2-control"],
                "ports": [{"host_ip": "127.0.0.1", "published": str(port), "target": 8000}],
            }
            for service, port in (
                ("aiops2-core", 17777),
                ("aiops2-glpi", 18080),
                ("aiops2-n8n", 15678),
                ("aiops2-prometheus", 19090),
                ("aiops2-grafana", 13000),
                ("aiops2-alertmanager", 19093),
            )
        },
        "networks": {"aiops2-control": {"name": stack + "-control", "internal": True}},
        "volumes": {"aiops2-postgres-data": {"name": stack + "-postgres-data"}},
    }


class IsolatedDeploymentPlanTests(unittest.TestCase):
    def test_valid_isolated_plan_does_not_expose_secret(self):
        result = ISOLATION.plan(env_fixture(), expected_stack="aiops2-rebuild")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["bind"], "loopback")
        self.assertFalse(result["legacy_services_touched"])
        self.assertNotIn("private-unittest-value", json.dumps(result))

    def test_default_production_identity_rejected(self):
        env = env_fixture()
        env["AIOPS_STACK_ID"] = env["COMPOSE_PROJECT_NAME"] = "aiops2"
        with self.assertRaises(ISOLATION.IsolationError):
            ISOLATION.plan(env)

    def test_compose_identity_mismatch_rejected(self):
        env = env_fixture()
        env["COMPOSE_PROJECT_NAME"] = "old-aiops"
        with self.assertRaisesRegex(ISOLATION.IsolationError, "identity"):
            ISOLATION.plan(env)

    def test_wildcard_and_public_ip_refused(self):
        for ip in ("0.0.0.0", "::", "10.0.0.1", "192.168.1.2"):
            with self.subTest(ip=ip):
                env = env_fixture()
                env["AIOPS_BIND_IP"] = ip
                with self.assertRaises(ISOLATION.IsolationError):
                    ISOLATION.plan(env)

    def test_duplicate_and_privileged_ports_rejected(self):
        env = env_fixture()
        env["AIOPS_GLPI_HOST_PORT"] = env["AIOPS_PORTAL_HOST_PORT"]
        with self.assertRaisesRegex(ISOLATION.IsolationError, "duplicate_host_port"):
            ISOLATION.plan(env)
        env["AIOPS_GLPI_HOST_PORT"] = "80"
        with self.assertRaisesRegex(ISOLATION.IsolationError, "port_out_of_range"):
            ISOLATION.plan(env)

    def test_duplicate_env_key_rejected_without_echoing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / ".env"
            path.write_text("POSTGRES_PASSWORD=super-secret\nPOSTGRES_PASSWORD=other-secret\n")
            with self.assertRaisesRegex(ISOLATION.IsolationError, "duplicate_env_key"):
                ISOLATION.read_env(path)

    def test_valid_resolved_compose_topology_passes(self):
        plan = ISOLATION.plan(env_fixture())
        result = ISOLATION.verify_compose(compose_fixture(), plan)
        self.assertTrue(result["resolved_compose_valid"])
        self.assertEqual(result["services"], 6)

    def test_external_networks_and_host_privilege_rejected(self):
        model = compose_fixture()
        model["networks"]["aiops2-control"]["external"] = True
        with self.assertRaisesRegex(ISOLATION.IsolationError, "external_networks"):
            ISOLATION.verify_compose(model, ISOLATION.plan(env_fixture()))
        model = compose_fixture()
        model["services"]["aiops2-core"]["privileged"] = True
        with self.assertRaisesRegex(ISOLATION.IsolationError, "privileged_service"):
            ISOLATION.verify_compose(model, ISOLATION.plan(env_fixture()))

    def test_foreign_volume_or_container_rejected(self):
        model = compose_fixture()
        model["volumes"]["aiops2-postgres-data"]["name"] = "aiops2-postgres-data"
        with self.assertRaisesRegex(ISOLATION.IsolationError, "unisolated_volumes"):
            ISOLATION.verify_compose(model, ISOLATION.plan(env_fixture()))
        model = compose_fixture()
        model["services"]["aiops2-core"]["container_name"] = "aiops2-core"
        with self.assertRaisesRegex(ISOLATION.IsolationError, "unisolated_container"):
            ISOLATION.verify_compose(model, ISOLATION.plan(env_fixture()))

    def test_nonloopback_compose_host_port_rejected(self):
        model = compose_fixture()
        model["services"]["aiops2-core"]["ports"][0]["host_ip"] = "0.0.0.0"
        with self.assertRaisesRegex(ISOLATION.IsolationError, "port_published_outside_loopback"):
            ISOLATION.verify_compose(model, ISOLATION.plan(env_fixture()))

    def test_unexpected_extra_published_port_is_rejected(self):
        model = compose_fixture()
        model["services"]["aiops2-core"]["ports"].append(
            {"host_ip": "127.0.0.1", "published": "19999", "target": 818}
        )
        with self.assertRaisesRegex(ISOLATION.IsolationError, "published_port_set_differs"):
            ISOLATION.verify_compose(model, ISOLATION.plan(env_fixture()))

    def test_duplicate_published_host_port_is_rejected(self):
        model = compose_fixture()
        model["services"]["aiops2-core"]["ports"].append(
            {"host_ip": "127.0.0.1", "published": "18080", "target": 9191}
        )
        with self.assertRaisesRegex(ISOLATION.IsolationError, "duplicate_resolved"):
            ISOLATION.verify_compose(model, ISOLATION.plan(env_fixture()))

    def test_cli_configure_only_produces_no_secret_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / ".env"
            path.write_text("\n".join(f"{k}={v}" for k, v in env_fixture().items()) + "\n")
            result = pathlib.Path(tmp) / "plan.json"
            exit_code = ISOLATION.main(["--env", str(path), "--expected-stack", "aiops2-rebuild", "--output", str(result)])
            self.assertEqual(exit_code, 0)
            self.assertTrue(result.is_file())
            self.assertNotIn("private-unittest-value", result.read_text())


if __name__ == "__main__":
    unittest.main()
