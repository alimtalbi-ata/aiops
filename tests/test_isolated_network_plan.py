"""Unit tests for the read-only offline network plan checker."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("network_plan", ROOT / "deploy/validate-isolated-network-plan.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NetworkPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "networks": {"control": "172.30.90.0/24", "data": "172.30.91.0/24"},
            "services": {
                "core": {"control": "172.30.90.10", "data": "172.30.91.10"},
                "postgres": {"data": "172.30.91.11"},
                "worker": {"control": "172.30.90.12"},
            },
            "dependencies": [
                {"from": "core", "to": "postgres"},
                {"from": "worker", "to": "core"},
            ],
        }
        self.inventory = {"routes": ["0.0.0.0/0", "10.79.94.0/24"],
                          "docker_networks": ["172.17.0.0/16"]}

    def check(self):
        return module.validate(self.plan, self.inventory)

    def test_valid_nonoverlapping_plan(self):
        self.assertEqual(self.check(), [])

    def test_existing_route_collision(self):
        self.inventory["routes"].append("172.30.90.0/24")
        self.assertTrue(any("existing_subnet_overlap" in x for x in self.check()))

    def test_docker_network_collision(self):
        self.inventory["docker_networks"].append("172.30.91.0/24")
        self.assertTrue(any("existing_subnet_overlap" in x for x in self.check()))

    def test_duplicate_ip(self):
        self.plan["services"]["worker"]["control"] = "172.30.90.10"
        self.assertTrue(any("duplicate_attachment_ip" in x for x in self.check()))

    def test_missing_route_to_dependency(self):
        self.plan["services"]["worker"] = {"data": "172.30.91.12"}
        self.plan["dependencies"] = [{"from": "worker", "to": "core"}]
        self.plan["services"]["core"] = {"control": "172.30.90.10"}
        self.assertTrue(any("unreachable_dependency" in x for x in self.check()))

    def test_empty_inventory_fails_closed(self):
        self.inventory["docker_networks"] = []
        self.assertIn("empty_inventory_refused", self.check())

    def test_invalid_ip(self):
        self.plan["services"]["core"]["control"] = "172.30.99.10"
        self.assertTrue(any("invalid_attachment_ip" in x for x in self.check()))


if __name__ == "__main__":
    unittest.main()
