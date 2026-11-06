"""Run with python -m unittest tests.test_fs364_ticket_verification."""
import unittest
from dataclasses import replace
from app.core.fs364_correlation import Link
from app.core.fs364_ticket_verification import Ticket147Snapshot, ticket147_matches


class Ticket147ContractTests(unittest.TestCase):
    def setUp(self):
        self.link = Link('fp', 'INC-DEMO-FS-001', 'RUN-4FABD1786F107E51',
                         'EVD-D2069BA816126499', 147, 'DEMO')
        self.ticket = Ticket147Snapshot(147, 1, 'AIOPS2-REAL-FS-20261106',
                                        'tenant-A', self.link.incident_id, True)

    def check(self, ticket=None, **kwargs):
        return ticket147_matches(self.link, ticket or self.ticket,
                                 expected_tenant_id=kwargs.get('tenant', 'tenant-A'),
                                 authenticated=kwargs.get('auth', True),
                                 acl_ok=kwargs.get('acl', True))

    def test_valid_backend_snapshot(self):
        self.assertTrue(self.check())

    def test_wrong_ticket_and_historical_validation(self):
        self.assertFalse(self.check(replace(self.ticket, ticket_id=146)))
        self.assertFalse(self.check(replace(self.ticket, ticket_id=True)))

    def test_wrong_tenant_or_incident(self):
        self.assertFalse(self.check(replace(self.ticket, tenant_id='tenant-B')))
        self.assertFalse(self.check(replace(self.ticket, incident_id='INC-OTHER')))

    def test_missing_glpi_get_and_wrong_reference(self):
        self.assertFalse(self.check(replace(self.ticket, fetched_from_glpi=False)))
        self.assertFalse(self.check(replace(self.ticket, reference='unverified')))

    def test_acl_and_identity_required(self):
        self.assertFalse(self.check(auth=False))
        self.assertFalse(self.check(acl=False))
        self.assertFalse(self.check(tenant=''))

    def test_demo_live_not_interchangeable(self):
        self.assertFalse(self.check(replace(self.ticket, ticket_type=2)))
        self.assertFalse(ticket147_matches(replace(self.link, mode='INVALID'), self.ticket,
                                            expected_tenant_id='tenant-A',
                                            authenticated=True, acl_ok=True))


if __name__ == '__main__':
    unittest.main()
