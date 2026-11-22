import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.actor_read_policy import Principal, Role, allows_read


class ActorReadPolicyTests(unittest.TestCase):
    def test_role_matrix(self):
        expected = {
            Role.N1: {"incident.read", "run.read"},
            Role.N2: {"incident.read", "run.read", "evidence.read"},
            Role.N3: {"incident.read", "run.read", "evidence.read", "decision.read"},
            Role.MANAGER: {"incident.read", "run.read", "decision.read"},
        }
        for role, allowed in expected.items():
            for permission in ("incident.read", "run.read", "evidence.read", "decision.read", "live.execute", "incident.write"):
                with self.subTest(role=role, permission=permission):
                    self.assertEqual(allows_read(Principal("actor-a", "tenant-a", role), "tenant-a", permission), permission in allowed)

    def test_cross_tenant_denied_for_every_role(self):
        for role in Role:
            self.assertFalse(allows_read(Principal("actor-a", "tenant-a", role), "tenant-b", "incident.read"))

    def test_missing_or_untrusted_shape_denied(self):
        for principal in (None, {}, Principal("", "tenant-a", Role.N3), Principal("actor-a", "", Role.N3), Principal("actor-a", "tenant-a", "N3")):
            self.assertFalse(allows_read(principal, "tenant-a", "incident.read"))
        self.assertFalse(allows_read(Principal("actor-a", "tenant-a", Role.N3), "", "incident.read"))
