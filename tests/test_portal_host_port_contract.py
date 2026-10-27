"""Offline contract for the single-portal host-port default."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PortalHostPortContractTests(unittest.TestCase):
    def test_compose_defaults_portal_to_target_port_and_loopback(self):
        compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
        self.assertIn(
            '${AIOPS_BIND_IP:-127.0.0.1}:${AIOPS_PORTAL_HOST_PORT:-17777}:777',
            compose,
        )
        self.assertNotIn("AIOPS_PORTAL_HOST_PORT:-7777", compose)


if __name__ == "__main__":
    unittest.main()
