from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class IsolatedComposeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = (ROOT / "compose.isolated.yml").read_text()
        cls.installer = (ROOT / "deploy/install-isolated.sh").read_text()
        cls.qualification = (ROOT / "tests/qualification-isolated.sh").read_text()

    def test_standalone_manifest_has_no_fixed_container_names(self):
        self.assertRegex(self.compose, r"(?m)^name: aiops2-isolated$")
        services = re.findall(r"^  (aiops2-[a-z0-9-]+):$", self.compose, re.M)
        self.assertEqual(len(services), 18)

    def test_every_published_port_is_loopback_only_and_exact(self):
        port_lines = [line.strip() for line in self.compose.splitlines() if "ports:" in line]
        self.assertEqual(len(port_lines), 6)
        expected = {
            'ports: ["127.0.0.1:17777:777"]',
            'ports: ["127.0.0.1:19090:9090"]',
            'ports: ["127.0.0.1:13000:3000"]',
            'ports: ["127.0.0.1:19093:9093"]',
            'ports: ["127.0.0.1:18080:80"]',
            'ports: ["127.0.0.1:15678:5678"]',
        }
        self.assertEqual(set(port_lines), expected)

    def test_named_volumes_and_networks_are_unique(self):
        for name in (
            "aiops2-isolated_postgres_data",
            "aiops2-isolated_temporal_postgres_data",
            "aiops2-isolated_prometheus_data",
            "aiops2-isolated_grafana_data",
            "aiops2-isolated_glpi_db_data",
            "aiops2-isolated_glpi_data",
            "aiops2-isolated_n8n_data",
            "aiops2-isolated_public",
            "aiops2-isolated_control",
            "aiops2-isolated_data",
            "aiops2-isolated_execution",
            "aiops2-isolated_temporal_data",
            "aiops2-isolated_integration",
            "aiops2-isolated_observability",
        ):
            with self.subTest(name=name):
                self.assertIn("name: " + name, self.compose)

    def test_installer_uses_only_standalone_manifest_and_fails_closed(self):
        self.assertIn('-f compose.isolated.yml', self.installer)
        self.assertNotIn('-f compose.yml', self.installer)
        self.assertIn("--no-build --pull never", self.installer)
        self.assertIn("image_not_preloaded", self.installer)
        self.assertIn("volume_already_exists", self.installer)
        self.assertIn("network_already_exists", self.installer)
        self.assertIn("project_containers_already_exist", self.installer)
        self.assertIn("10.79.94.202", self.installer)
        self.assertNotIn("docker compose down", self.installer)
        self.assertNotIn("docker volume rm", self.installer)
        self.assertNotIn("RETIRE_LEGACY=1", self.installer)

    def test_internal_dns_is_preserved_and_consumers_share_networks(self):
        # Docker embedded service-name resolution is explicitly allowed.
        service_blocks = {}
        for name, body in re.findall(
            r"(?ms)^  (aiops2-[a-z0-9-]+):\\n(.*?)(?=^  aiops2-[a-z0-9-]+:|^networks:)",
            self.compose,
        ):
            service_blocks[name] = body
        self.assertEqual(len(service_blocks), 18)
        for consumer, target, network in (
            ("aiops2-n8n", "aiops2-postgres", "aiops2-integration"),
            ("aiops2-simulator", "aiops2-core", "aiops2-control"),
            ("aiops2-core", "aiops2-postgres", "aiops2-data"),
            ("aiops2-worker", "aiops2-temporal", "aiops2-control"),
            ("aiops2-portal", "aiops2-core", "aiops2-control"),
            ("aiops2-glpi", "aiops2-glpi-db", "aiops2-integration"),
        ):
            with self.subTest(consumer=consumer, target=target):
                self.assertIn(network, service_blocks[consumer].split("    networks:", 1)[1].split("\\n", 1)[0])
                self.assertIn(network, service_blocks[target].split("    networks:", 1)[1].split("\\n", 1)[0])
        self.assertIn("DB_POSTGRESDB_HOST: aiops2-postgres", service_blocks["aiops2-n8n"])
        self.assertIn("CORE_URL: http://aiops2-core:810", service_blocks["aiops2-simulator"])

    def test_runtime_qualification_checks_loopback_bindings(self):
        self.assertIn('HostIp', self.qualification)
        self.assertIn('"127.0.0.1"', self.qualification)
        self.assertIn("ISOLATED_QUALIFICATION=PASS", self.qualification)


if __name__ == "__main__":
    unittest.main()
