import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[2]/"scripts/ops/usecase_acceptance.py"
s=importlib.util.spec_from_file_location("acceptance",p)
m=importlib.util.module_from_spec(s)
s.loader.exec_module(m)

def fixture(status="BLOCKED",linked=False):
    return {"run_id":"RUN-8CA56A39E58944F1",
      "checks":{"core_run":"PASS","core_api":"PASS","evidence_api":"PASS",
                "critic_policy_outbox":"PASS","itsm_readback":"PASS" if linked else "UNVERIFIED",
                "temporal_worker_execution":"UNVERIFIED","hitl_action_binding":"UNVERIFIED"},
      "core":{"run":{"status":status}},
      "database":{"run":{"status":status},
                  "critic_outbox":[{"status":"RECONCILED","policy_decision_id":"POL-TEST"}],
                  "glpi_links":[{"glpi_ticket_id":201}] if linked else []},
      "external_glpi_observation":{"ticket_id":201}}

class TestAcceptance(unittest.TestCase):
    def test_safe_block_not_failure(self):
        a=m.assess(fixture())
        self.assertTrue(a["safe_block_confirmed"])
        self.assertEqual(a["verdict"],"HOLD")
        self.assertIn("temporal_worker_verified",a["unverified"])
    def test_user_observed_ticket_not_link(self):
        a=m.assess(fixture())
        self.assertFalse(a["assertions"]["itsm_link_verified"])
    def test_linked_ticket_still_not_full_e2e(self):
        a=m.assess(fixture(linked=True))
        self.assertTrue(a["assertions"]["itsm_link_verified"])
        self.assertEqual(a["verdict"],"HOLD")
    def test_no_policy_block_no_claim(self):
        a=m.assess(fixture(status="RUNNING"))
        self.assertFalse(a["safe_block_confirmed"])
    def test_empty_report_fails_closed(self):
        a=m.assess({})
        self.assertEqual(a["verdict"],"HOLD")

if __name__=="__main__":
    unittest.main()
