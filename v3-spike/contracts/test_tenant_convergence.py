import unittest
from hashlib import sha256
from tenant_convergence import Grant, TenantReadModel

class TenantContractTests(unittest.TestCase):
    def setUp(self):
        grants = {sha256(t.encode()).hexdigest(): Grant(t, tenant, frozenset(perms))
                  for t, tenant, perms in [
                      ("a", "A", ["incident:read"]), ("b", "B", ["incident:read"]),
                      ("denied", "A", [])]}
        self.model = TenantReadModel(grants,
            {("A", "same"): {"service": "payments"},
             ("B", "same"): {"service": "storage"},
             ("A", "private"): {"service": "network"}},
            {("A", "same"): ("proof-a",), ("B", "same"): ("proof-b",)})

    def test_collision(self):
        a, b = self.model.read("a", "same"), self.model.read("b", "same")
        self.assertEqual(a["service"], "payments")
        self.assertEqual(b["service"], "storage")
        self.assertEqual(a["evidence_ids"], ["proof-a"])
        self.assertEqual(b["evidence_ids"], ["proof-b"])

    def test_cross_tenant(self):
        with self.assertRaises(LookupError):
            self.model.read("b", "private")

    def test_missing_and_cross_tenant_same_error(self):
        for incident in ("private", "missing"):
            with self.assertRaisesRegex(LookupError, "^NOT_FOUND$"):
                self.model.read("b", incident)

    def test_unknown_token(self):
        with self.assertRaises(PermissionError):
            self.model.read("unknown", "same")

    def test_no_permission(self):
        with self.assertRaises(PermissionError):
            self.model.read("denied", "same")

    def test_missing_evidence(self):
        result = self.model.read("a", "private")
        self.assertEqual(result["evidence_ids"], [])
        self.assertEqual(result["rca"], "UNKNOWN")
        self.assertFalse(result["live_remediation_authorized"])

if __name__ == "__main__":
    unittest.main()
