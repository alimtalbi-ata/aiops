import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"tools/generate_acme_payroll_freeze_v298.py"
spec=importlib.util.spec_from_file_location("payroll",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class PayrollTests(unittest.TestCase):
    def test_freeze_never_authorizes_restart(self):
        data=m.generate()
        self.assertEqual(data["effects"]["restarts"],0)
        self.assertEqual(data["effects"]["approvals_granted"],0)
        self.assertTrue(all(x["scope"]=="ACME" and x["synthetic"] for x in data["events"]))
        approvals=[x for x in data["events"] if x["kind"]=="policy_decision"]
        self.assertEqual(approvals[0]["decision"],"HUMAN_APPROVAL")
        self.assertFalse(approvals[0]["execution_allowed"])
    def test_glpi_not_fabricated(self):
        data=m.generate()
        self.assertEqual(data["effects"]["glpi_tickets_created"],0)
        self.assertTrue(any(x.get("glpi_status")=="NOT_CREATED" for x in data["events"]))
    def test_unconfirmed_causality_and_human_messages(self):
        data=m.generate()
        self.assertEqual(data["grounding"]["load_balancer_causality"],"HYPOTHESIS_NOT_CONFIRMED")
        self.assertTrue(any(x["actor"].startswith("Claire") for x in data["events"]))
        self.assertTrue(any(x["kind"]=="approval_pending" for x in data["events"]))
if __name__=="__main__":unittest.main()
