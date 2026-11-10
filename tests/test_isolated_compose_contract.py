from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class IsolatedComposeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay = (ROOT / "compose.isolated.yml").read_text()
        cls.installer = (ROOT / "deploy/install-isolated.sh").read_text()

    def test_every_service_removes_fixed_container_name(self):
        base = (ROOT / "compose.yml").read_text()
        services = re.findall(r"^  (aiops2-[a-z0-9-]+):$", base, re.M)
        for service in services:
            with self.subTest(service=service):
                block = re.search(
                    rf"^  {re.escape(service)}:\n(?P<body>.*?)(?=^  aiops2-[a-z0-9-]+:|^networks:)",
                    self.overlay,
                    re.M | re.S,
                )
                self.assertIsNotNone(block, f"missing isolated override for {service}")
                self.assertRegex(block.group("body"), r"(?m)^    container_name: null$")

    def test_all_published_ports_are_loopback_only(self):
        expected = {
            "127.0.0.1:17777:777",
            "127.0.0.1:18080:80",
            "127.0.0.1:15678:5678",
            "127.0.0.1:19090:9090",
            "127.0.0.1:13000:3000",
            "127.0.0.1:19093:9093",
        }
        for binding in expected:
            with self.subTest(binding=binding):
                self.assertIn(f'"{binding}"', self.overlay)
        self.assertNotRegex(self.overlay, r'"(?:0\.0\.0\.0|\[::\]):')

    def test_all_named_volumes_and_networks_are_namespaced(self):
        self.assertIn("${AIOPS_ISOLATION_ID:?AIOPS_ISOLATION_ID_required}_postgres_data", self.overlay)
        self.assertIn("${AIOPS_ISOLATION_ID:?AIOPS_ISOLATION_ID_required}_n8n_data", self.overlay)
        self.assertIn("${AIOPS_ISOLATION_ID:?AIOPS_ISOLATION_ID_required}_public", self.overlay)
        self.assertIn("${AIOPS_ISOLATION_ID:?AIOPS_ISOLATION_ID_required}_observability", self.overlay)

    def test_installer_is_offline_and_fail_closed(self):
        self.assertIn("--no-build --pull never", self.installer)
        self.assertIn("image_not_preloaded", self.installer)
        self.assertIn("volume_already_exists", self.installer)
        self.assertIn("network_already_exists", self.installer)
        self.assertIn("project_containers_already_exist", self.installer)
        self.assertNotIn("docker compose down", self.installer)
        self.assertNotIn("docker volume rm", self.installer)
        self.assertNotIn("RETIRE_LEGACY=1", self.installer)


if __name__ == "__main__":
    unittest.main()
