"""FS364 GLPI 147 fail-closed boundary: injected backend failures, no host access."""
import unittest

from app.core.fs364_correlation import Link
from app.core.fs364_glpi_read_boundary import verify_ticket147_readonly


class Ticket147BackendFailureTests(unittest.TestCase):
    def setUp(self):
        self.link = Link("fp", "INC-DEMO-FS-001", "RUN-4FABD1786F107E51",
                         "EVD-D2069BA816126499", 147, "DEMO")
        self.ticket = {"id": 147, "type": 1, "name": "AIOPS2-REAL-FS-20261106", "is_deleted": 0}

    def verify(self, get, owner, acl):
        return verify_ticket147_readonly(
            self.link, tenant_id="tenant-A", actor_id="actor-A",
            glpi_get=get, authoritative_owner=owner, authorize_actor=acl)

    def test_backend_failures_never_admit(self):
        def broken(*_):
            raise TimeoutError("backend timeout")
        valid_get = lambda _: self.ticket
        valid_owner = lambda _: ("tenant-A", self.link.incident_id)
        valid_acl = lambda *_: True
        for adapters in ((broken, valid_owner, valid_acl),
                         (valid_get, broken, valid_acl),
                         (valid_get, valid_owner, broken)):
            with self.subTest(failed=adapters.index(broken)):
                self.assertIs(self.verify(*adapters), False)

    def test_malformed_ticket_responses_never_admit(self):
        for ticket in (None, [], "147", {}, {"id": 147}, {"id": True, "type": 1,
                       "name": "AIOPS2-REAL-FS-20261106"}):
            with self.subTest(ticket=ticket):
                self.assertIs(self.verify(
                    lambda _: ticket,
                    lambda _: ("tenant-A", self.link.incident_id),
                    lambda *_: True), False)

    def test_acl_denial_prevents_glpi_and_ownership_reads(self):
        for decision in (False, None, 1, "true", {}, []):
            with self.subTest(decision=decision):
                reads = []
                def get_ticket(*args):
                    reads.append(("glpi", args))
                    return self.ticket
                def get_owner(*args):
                    reads.append(("owner", args))
                    return ("tenant-A", self.link.incident_id)
                self.assertIs(self.verify(get_ticket, get_owner,
                                          lambda *_: decision), False)
                self.assertEqual(reads, [], "ACL denial must not expose ticket or owner")

    def test_acl_error_prevents_glpi_and_ownership_reads(self):
        reads = []
        def forbidden_read(*_):
            reads.append("read")
            raise AssertionError("read after ACL error")
        def failed_acl(*_):
            raise PermissionError("denied")
        self.assertIs(self.verify(forbidden_read, forbidden_read, failed_acl), False)
        self.assertEqual(reads, [])

    def test_invalid_tenant_prevents_all_backend_reads(self):
        calls = []
        def observed(*args):
            calls.append(args)
            return self.ticket
        for tenant in ("", " tenant-A", "tenant-A ", None):
            with self.subTest(tenant=tenant):
                self.assertIs(verify_ticket147_readonly(
                    self.link, tenant_id=tenant, actor_id="actor-A",
                    glpi_get=observed, authoritative_owner=observed,
                    authorize_actor=observed), False)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
