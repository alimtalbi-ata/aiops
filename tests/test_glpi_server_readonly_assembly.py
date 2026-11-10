"""Offline assembly contract: missing trust must never contact upstreams."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_server_readonly_assembly import make_server_glpi_readonly_qualifier
from shared.glpi_hmac_qualification import GLPIHmacQualificationBlocked


class AssemblyTests(unittest.TestCase):
    def config(self):
        def denied(**kwargs):
            return False
        def missing(**kwargs):
            raise AssertionError("untrusted dependency called")
        return dict(secret=b"s" * 32, fetch_signed_event=missing,
                    consume_nonce=missing, authorize_actor=denied,
                    authorize_read=denied, core_token=missing,
                    glpi_app_token=missing, glpi_user_token=missing, core_base_url="https://core.internal",
                    glpi_base_url="https://glpi.internal")

    def test_missing_trust_refused_at_construction(self):
        for key, value in (("secret", b"short"), ("fetch_signed_event", None),
                           ("consume_nonce", None), ("authorize_actor", None),
                           ("authorize_read", None), ("core_token", None),
                           ("glpi_app_token", None), ("glpi_user_token", None)):
            with self.subTest(key=key):
                config = self.config()
                config[key] = value
                with self.assertRaises(ValueError):
                    make_server_glpi_readonly_qualifier(**config)

    def test_shared_origin_rejected(self):
        config = self.config()
        config["glpi_base_url"] = config["core_base_url"]
        with self.assertRaises(ValueError):
            make_server_glpi_readonly_qualifier(**config)

    def test_signed_event_unavailable_blocks_before_http(self):
        qualify = make_server_glpi_readonly_qualifier(**self.config())
        with self.assertRaises(GLPIHmacQualificationBlocked):
            qualify(actor="operator", tenant_id="tenant-a", ticket_id="201")


if __name__ == "__main__":
    unittest.main()
