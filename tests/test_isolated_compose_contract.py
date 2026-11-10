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
        cls.prometheus = (ROOT / "config/isolated/prometheus/prometheus.yml").read_text()
        cls.grafana = (ROOT / "config/isolated/grafana/provisioning/datasources/datasource.yml").read_text()

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


    def test_all_runtime_service_endpoints_use_static_ipv4_not_service_dns(self):
        for forbidden in (
            "http://aiops2-", "@aiops2-", "POSTGRES_SEEDS: aiops2-",
            "TEMPORAL_ADDRESS: aiops2-", "GLPI_DB_HOST: aiops2-",
            "DB_POSTGRESDB_HOST: aiops2-", "CORE_URL: http://aiops2-",
            "COPILOT_URL: http://aiops2-", "TWIN_URL: http://aiops2-",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.compose)
        self.assertIn("http://172.30.60.2:9090", self.grafana)
        self.assertIn("172.30.10.10:810", self.prometheus)
        self.assertIn("172.30.10.15:815", self.prometheus)
        self.assertIn("./config/isolated/prometheus:/etc/prometheus:ro", self.compose)
        self.assertIn("./config/isolated/grafana/provisioning:/etc/grafana/provisioning:ro", self.compose)

    def test_static_ipam_is_declared_and_all_service_ips_are_unique(self):
        subnets = re.findall(r"subnet: (172\\.30\\.\\d+\\.0/24)", self.compose)
        self.assertEqual(set(subnets), {
            "172.30.10.0/24", "172.30.20.0/24", "172.30.30.0/24",
            "172.30.40.0/24", "172.30.50.0/24", "172.30.60.0/24",
            "172.30.70.0/24",
        })
        addresses = re.findall(r"ipv4_address: (172\\.30\\.\\d+\\.\\d+)", self.compose)
        self.assertGreaterEqual(len(addresses), 25)
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertIn("subnet_collision", self.installer)
        self.assertIn("docker network inspect", self.installer)

    def test_runtime_qualification_checks_loopback_bindings(self):
        self.assertIn('HostIp', self.qualification)
        self.assertIn('"127.0.0.1"', self.qualification)
        self.assertIn("ISOLATED_QUALIFICATION=PASS", self.qualification)


if __name__ == "__main__":
    unittest.main()
