import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[2]/"scripts/ops/itsm_link_diagnosis.py"
s=importlib.util.spec_from_file_location("itsm",p)
m=importlib.util.module_from_spec(s)
s.loader.exec_module(m)
def sample():
    return {"run_id":"RUN-TEST123456","database":{"run":{"incident_id":"INC-TEST"},
            "glpi_links":[],"itsm_xref":[]},"checks":{"glpi_core_link":"MISSING"},
            "external_glpi_observation":{"ticket_id":201}}
class TestDiagnosis(unittest.TestCase):
    def test_actual_failure_is_unverified_not_duplicate_creation(self):
        r=m.diagnose(sample())
        self.assertEqual(r["cause"],"CORE_LINK_ABSENT_GLPI_UNVERIFIED")
        self.assertEqual(r["verdict"],"HOLD")
    def test_glpi_match_without_core_link_is_not_pass(self):
        r=m.diagnose(sample(),{"ticket":{"readback":"MATCHED_MARKER"}})
        self.assertEqual(r["cause"],"GLPI_MARKERS_MATCH_CORE_LINK_ABSENT")
        self.assertEqual(r["verdict"],"HOLD")
    def test_different_link_must_not_be_overwritten(self):
        a=sample()
        a["database"]["glpi_links"]=[{"glpi_ticket_id":202,"state":"CONFIRMED"}]
        self.assertEqual(m.diagnose(a)["cause"],"DIFFERENT_TICKET_LINKED")
    def test_link_present_but_not_confirmed(self):
        a=sample()
        a["database"]["glpi_links"]=[{"glpi_ticket_id":201,"state":"PENDING"}]
        self.assertEqual(m.diagnose(a)["cause"],"LINK_PRESENT_NOT_CONFIRMED")
    def test_full_matching_xref_required(self):
        a=sample()
        a["database"]["glpi_links"]=[{"glpi_ticket_id":201,"state":"CONFIRMED"}]
        a["database"]["itsm_xref"]=[{"ticket_id":201,"glpi_ticket_readback_verified":True}]
        self.assertEqual(m.diagnose(a)["verdict"],"PASS")
    def test_other_ticket_xref_cannot_pass(self):
        a=sample()
        a["database"]["glpi_links"]=[{"glpi_ticket_id":201,"state":"CONFIRMED"}]
        a["database"]["itsm_xref"]=[{"ticket_id":202,"glpi_ticket_readback_verified":True}]
        self.assertEqual(m.diagnose(a)["verdict"],"HOLD")
    def test_xref_without_link_is_actionable(self):
        a=sample()
        a["database"]["itsm_xref"]=[{"ticket_id":201,"glpi_ticket_readback_verified":True}]
        self.assertEqual(m.diagnose(a)["cause"],"XREF_WITHOUT_CORE_LINK")
if __name__=="__main__":
    unittest.main()
