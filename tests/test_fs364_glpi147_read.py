"""FS364 read-only GLPI 147 boundary regression tests."""
import unittest
from integration.fs364_glpi147_read import verify_ticket147, VerificationDenied

class TestGLPI147Boundary(unittest.TestCase):
    def setUp(self):
        self.ticket = {"id":147,"type":1,"name":"AIOPS2-REAL-FS-20261106","tenant_id":"tenant-a","incident_ref":"INC-LAB","is_deleted":0}
        self.kw = dict(tenant_id="tenant-a",actor_id="actor-a",incident_ref="INC-LAB")

    def verify(self, ticket=None, acl=True, **overrides):
        return verify_ticket147(
            get_ticket=lambda i: self.ticket if ticket is None else ticket,
            authorize=lambda *args: acl, **dict(self.kw, **overrides))

    def test_valid_read(self):
        self.assertEqual(self.verify().ticket_id,147)

    def test_wrong_ticket(self):
        with self.assertRaises(VerificationDenied):
            self.verify(ticket=dict(self.ticket,id=146))

    def test_rejects_ambiguous_native_identity(self):
        for changes in ({"id":"147"}, {"id":True}, {"type":2},
                        {"type":True}, {"name":"AIOPS2-REAL-FS-OTHER"},
                        {"name":None}):
            with self.subTest(changes=changes):
                with self.assertRaises(VerificationDenied):
                    self.verify(ticket=dict(self.ticket, **changes))

    def test_wrong_tenant(self):
        with self.assertRaises(VerificationDenied):
            self.verify(tenant_id="tenant-b")

    def test_wrong_incident(self):
        with self.assertRaises(VerificationDenied):
            self.verify(incident_ref="OTHER")

    def test_truthy_acl_rejected(self):
        with self.assertRaises(VerificationDenied):
            self.verify(acl="true")

    def test_missing_deletion_state(self):
        with self.assertRaises(VerificationDenied):
            self.verify(ticket={k:v for k,v in self.ticket.items() if k!="is_deleted"})

    def test_acl_denial_does_not_read(self):
        calls=[]
        with self.assertRaises(VerificationDenied):
            verify_ticket147(get_ticket=lambda i:calls.append(i),
                              authorize=lambda *a:False, **self.kw)
        self.assertEqual(calls,[])

    def test_transport_failure(self):
        def fail(i): raise ConnectionError()
        with self.assertRaises(VerificationDenied):
            verify_ticket147(get_ticket=fail,authorize=lambda *a:True,**self.kw)

if __name__=="__main__":
    unittest.main()
