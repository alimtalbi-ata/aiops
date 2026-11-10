"""Offline GET-only Core/GLPI adapter ACL and URL contract tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_http_readers import GLPIHTTPReadBlocked, make_core_glpi_readers


class HTTPReadersTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.allowed = True

    def acl(self, **kwargs):
        self.calls.append(("acl", kwargs))
        return self.allowed

    def core(self, **kwargs):
        self.calls.append(("core", kwargs))
        return {"run": {"run_id": "RUN-12345678"}}

    def glpi(self, **kwargs):
        self.calls.append(("glpi", kwargs))
        return {"id": 201}

    def readers(self, **kwargs):
        args = dict(core_base_url="https://core.internal",
                    glpi_base_url="https://glpi.internal",
                    core_get=self.core, glpi_get=self.glpi,
                    authorize_read=self.acl)
        args.update(kwargs)
        return make_core_glpi_readers(**args)

    def test_get_paths_and_acl_before_request(self):
        core, glpi = self.readers()
        core(actor="operator", tenant_id="tenant-a", run_id="RUN-12345678")
        glpi(actor="operator", tenant_id="tenant-a",
             ticket_id="201", glpi_instance_id="ci")
        self.assertEqual([call[0] for call in self.calls],
                         ["acl", "core", "acl", "glpi"])
        self.assertEqual(self.calls[1][1]["url"],
                         "https://core.internal/api/runs/RUN-12345678")
        self.assertEqual(self.calls[3][1]["url"],
                         "https://glpi.internal/Ticket/201")

    def test_denied_acl_prevents_network(self):
        self.allowed = False
        core, glpi = self.readers()
        with self.assertRaises(GLPIHTTPReadBlocked):
            core(actor="operator", tenant_id="tenant-a", run_id="RUN-12345678")
        with self.assertRaises(GLPIHTTPReadBlocked):
            glpi(actor="operator", tenant_id="tenant-a",
                 ticket_id="201", glpi_instance_id="ci")
        self.assertEqual([call[0] for call in self.calls], ["acl", "acl"])

    def test_bad_resource_ids_block_before_acl(self):
        core, glpi = self.readers()
        with self.assertRaises(GLPIHTTPReadBlocked):
            core(actor="operator", tenant_id="tenant-a", run_id="../etc/passwd")
        with self.assertRaises(GLPIHTTPReadBlocked):
            glpi(actor="operator", tenant_id="tenant-a",
                 ticket_id="201/../1", glpi_instance_id="ci")
        self.assertEqual(self.calls, [])

    def test_untrusted_endpoint_and_missing_acl_rejected(self):
        for changes in ({"core_base_url": "http://core.internal"},
                        {"glpi_base_url": "https://user@glpi.internal"},
                        {"authorize_read": None},
                        {"core_base_url": "https://core.internal/evil"},
                        {"core_base_url": "https://core.internal:invalid"},
                        {"core_base_url": "https://core.internal\\\\@evil.invalid"},
                        {"core_base_url": "https://core.internal:0"},
                        {"core_base_url": "https://core.internal?next=evil"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.readers(**changes)


if __name__ == "__main__":
    unittest.main()
