"""Offline FS364 GLPI read-boundary regression tests; no network or writes."""
import unittest

from app.core.fs364_correlation import Link
from app.core.fs364_glpi_read_boundary import verify_ticket147_readonly


class GLPIReadBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.link = Link("fp", "INC-DEMO-FS-001", "RUN-4FABD1786F107E51",
                         "EVD-D2069BA816126499", 147, "DEMO")
        self.calls = []
        self.ticket = {"id": 147, "type": 1, "name": "AIOPS2-REAL-FS-20261106", "is_deleted": 0}

    def check(self, ticket=None, owner=None, acl=True, actor="actor-A"):
        def get(number):
            self.calls.append(("GET", number))
            return self.ticket if ticket is None else ticket
        def owned(number):
            self.calls.append(("OWNER", number))
            return ("tenant-A", self.link.incident_id) if owner is None else owner
        def authorized(who, tenant, number):
            self.calls.append(("ACL", who, tenant, number))
            return acl
        return verify_ticket147_readonly(
            self.link, tenant_id="tenant-A", actor_id=actor,
            glpi_get=get, authoritative_owner=owned, authorize_actor=authorized)

    def test_read_only_positive_contract(self):
        self.assertTrue(self.check())
        self.assertEqual(self.calls, [("ACL", "actor-A", "tenant-A", 147),
                                      ("GET", 147), ("OWNER", 147)])

    def test_acl_denial_never_reads_glpi_or_ownership(self):
        for denied in (False, None, 1, "true"):
            with self.subTest(denied=denied):
                self.calls.clear()
                self.assertFalse(self.check(acl=denied))
                self.assertEqual(
                    self.calls, [("ACL", "actor-A", "tenant-A", 147)])

    def test_wrong_ticket_and_historical_146(self):
        for value in (146, "147", True, 148):
            with self.subTest(value=value):
                self.assertFalse(self.check(ticket={**self.ticket, "id": value}))

    def test_wrong_identity_never_reads_ownership(self):
        for field, value in (("id", 146), ("id", "147"), ("id", True),
                             ("type", 2), ("type", True),
                             ("name", "unrelated"), ("name", None)):
            with self.subTest(field=field, value=value):
                self.calls.clear()
                self.assertFalse(self.check(ticket={**self.ticket, field: value}))
                self.assertEqual(self.calls, [
                    ("ACL", "actor-A", "tenant-A", 147), ("GET", 147)])

    def test_deleted_or_unknown_deletion_state_never_reads_owner(self):
        for value in (1, True, "0", None):
            with self.subTest(value=value):
                self.calls.clear()
                self.assertFalse(self.check(ticket={**self.ticket, "is_deleted": value}))
                self.assertEqual(self.calls, [
                    ("ACL", "actor-A", "tenant-A", 147), ("GET", 147)])
        self.calls.clear()
        missing = {k: v for k, v in self.ticket.items() if k != "is_deleted"}
        self.assertFalse(self.check(ticket=missing))
        self.assertEqual(self.calls, [
            ("ACL", "actor-A", "tenant-A", 147), ("GET", 147)])

    def test_untrusted_owner_rejected(self):
        for owner in (("tenant-B", self.link.incident_id),
                      ("tenant-A", "INC-other"), None, ["tenant-A", self.link.incident_id]):
            with self.subTest(owner=owner):
                # Explicit None is covered by failure case via a malformed owner tuple.
                if owner is None:
                    owner = ()
                self.assertFalse(self.check(owner=owner))

    def test_acl_truthy_is_not_authorization(self):
        for acl in ("true", 1, None, False):
            with self.subTest(acl=acl):
                self.assertFalse(self.check(acl=acl))

    def test_invalid_actor_short_circuits_before_get(self):
        self.assertFalse(self.check(actor=" "))
        self.assertEqual(self.calls, [])

    def test_transport_failure_fails_closed(self):
        def unavailable(_):
            raise ConnectionError("GLPI unavailable")
        self.assertFalse(verify_ticket147_readonly(
            self.link, tenant_id="tenant-A", actor_id="actor-A",
            glpi_get=unavailable,
            authoritative_owner=lambda _: ("tenant-A", self.link.incident_id),
            authorize_actor=lambda *_: True))


if __name__ == "__main__":
    unittest.main()
