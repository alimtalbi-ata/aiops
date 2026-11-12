"""FS364 negative contract: GLPI 147 cannot be admitted on malformed identity facts.

These are local unit tests only; no authenticated GLPI GET or Debian execution.
"""
import unittest
from dataclasses import replace

from app.core.fs364_correlation import Link
from app.core.fs364_ticket_verification import Ticket147Snapshot, ticket147_matches


class Ticket147IdentityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.link = Link("fp", "INC-DEMO-FS-001", "RUN-4FABD1786F107E51",
                         "EVD-D2069BA816126499", 147, "DEMO")
        self.ticket = Ticket147Snapshot(147, 1, "AIOPS2-REAL-FS-20261106",
                                        "tenant-A", self.link.incident_id, True)

    def allowed(self, ticket=None, **overrides):
        facts = dict(expected_tenant_id="tenant-A", authenticated=True, acl_ok=True)
        facts.update(overrides)
        return ticket147_matches(self.link, ticket or self.ticket, **facts)

    def test_positive_reference_only_not_authorization(self):
        self.assertTrue(self.allowed())

    def test_truthy_strings_are_not_auth_or_acl(self):
        for field in ("authenticated", "acl_ok"):
            with self.subTest(field=field):
                self.assertFalse(self.allowed(**{field: "true"}))
                self.assertFalse(self.allowed(**{field: 1}))

    def test_provenance_boolean_must_be_exact(self):
        for value in ("true", 1, None):
            with self.subTest(value=value):
                self.assertFalse(self.allowed(replace(self.ticket, fetched_from_glpi=value)))

    def test_tenant_must_not_be_coerced_or_normalized(self):
        for tenant in (" tenant-A", "tenant-A ", "tenant-B", "", None, 123):
            with self.subTest(tenant=tenant):
                self.assertFalse(self.allowed(expected_tenant_id=tenant))

    def test_glpi_identity_fields_fail_closed(self):
        for field, value in (("ticket_id", "147"), ("ticket_type", True),
                             ("reference", None), ("incident_id", None),
                             ("tenant_id", None)):
            with self.subTest(field=field):
                self.assertFalse(self.allowed(replace(self.ticket, **{field: value})))


if __name__ == "__main__":
    unittest.main()
