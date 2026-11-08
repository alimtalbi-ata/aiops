import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy
p=Path(__file__).resolve().parents[2]/"scripts/ops/itsm_link_diagnosis.py"
s=importlib.util.spec_from_file_location("itsm",p)
m=importlib.util.module_from_spec(s)
s.loader.exec_module(m)
def sample():
    return {"run_id":"RUN-TEST123456","database":{"run":{"run_id":"RUN-TEST123456","incident_id":"INC-TEST"},
            "glpi_links":[],"itsm_xref":[]},"checks":{"glpi_core_link":"MISSING"},
            "external_glpi_observation":{"ticket_id":201}}
class TestDiagnosis(unittest.TestCase):
    def test_actual_failure_is_unverified_not_duplicate_creation(self):
        r=m.diagnose(sample())
        self.assertEqual(r["cause"],"CORE_LINK_ABSENT_GLPI_UNVERIFIED")
        self.assertEqual(r["verdict"],"HOLD")
    def test_glpi_match_without_core_link_is_not_pass(self):
        r=m.diagnose(sample(),{"run_id":"RUN-TEST123456","incident_id":"INC-TEST","ticket":{"ticket_id":201,"readback":"MATCHED_MARKER","ticket_id_verified":True,"ticket_active":True,"run_marker_present":True,"incident_marker_present":True}})
        self.assertEqual(r["cause"],"GLPI_MARKERS_MATCH_CORE_LINK_ABSENT")
        self.assertEqual(r["verdict"],"HOLD")
    def test_different_link_must_not_be_overwritten(self):
        a=sample()
        a["database"]["glpi_links"]=[{"incident_id":"INC-TEST","glpi_ticket_id":202,"state":"CONFIRMED"}]
        self.assertEqual(m.diagnose(a)["cause"],"DIFFERENT_TICKET_LINKED")
    def test_link_present_but_not_confirmed(self):
        a=sample()
        a["database"]["glpi_links"]=[{"incident_id":"INC-TEST","glpi_ticket_id":201,"state":"PENDING"}]
        self.assertEqual(m.diagnose(a)["cause"],"LINK_PRESENT_NOT_CONFIRMED")
    def test_full_matching_xref_required(self):
        a=sample()
        a["database"]["glpi_links"]=[{"incident_id":"INC-TEST","glpi_ticket_id":201,"state":"CONFIRMED"}]
        a["database"]["itsm_xref"]=[{"incident_id":"INC-TEST","ticket_id":201,"glpi_ticket_readback_verified":True}]
        self.assertEqual(m.diagnose(a)["verdict"],"PASS")
    def test_other_ticket_xref_cannot_pass(self):
        a=sample()
        a["database"]["glpi_links"]=[{"incident_id":"INC-TEST","glpi_ticket_id":201,"state":"CONFIRMED"}]
        a["database"]["itsm_xref"]=[{"incident_id":"INC-TEST","ticket_id":202,"glpi_ticket_readback_verified":True}]
        self.assertEqual(m.diagnose(a)["verdict"],"HOLD")
    def test_xref_without_link_is_actionable(self):
        a=sample()
        a["database"]["itsm_xref"]=[{"incident_id":"INC-TEST","ticket_id":201,"glpi_ticket_readback_verified":True}]
        self.assertEqual(m.diagnose(a)["cause"],"XREF_WITHOUT_CORE_LINK")
class IdentityRegressionTests(unittest.TestCase):
    def confirmed(self):
        a=sample()
        a["database"]["glpi_links"]=[{"incident_id":"INC-TEST","glpi_ticket_id":201,"state":"CONFIRMED"}]
        a["database"]["itsm_xref"]=[{"incident_id":"INC-TEST","ticket_id":201,"glpi_ticket_readback_verified":True}]
        return a

    def test_foreign_incident_or_run_never_passes(self):
        for group in ("glpi_links", "itsm_xref"):
            a=self.confirmed()
            a["database"][group][0]["incident_id"]="INC-FOREIGN"
            self.assertEqual(m.diagnose(a)["cause"],"IDENTITY_MISMATCH")
        a=self.confirmed()
        a["database"]["run"]["run_id"]="RUN-FOREIGN"
        self.assertEqual(m.diagnose(a)["verdict"],"HOLD")

    def test_foreign_readback_never_passes(self):
        a=self.confirmed()
        r={"run_id":"RUN-FOREIGN","incident_id":"INC-TEST","ticket":{"ticket_id":201,"readback":"MATCHED_MARKER"}}
        self.assertEqual(m.diagnose(a,r)["cause"],"IDENTITY_MISMATCH")

    def test_duplicate_and_conflicting_links_hold(self):
        for ticket in (201,202):
            a=self.confirmed()
            a["database"]["glpi_links"].append({"incident_id":"INC-TEST","glpi_ticket_id":ticket,"state":"CONFIRMED"})
            self.assertEqual(m.diagnose(a)["cause"],"AMBIGUOUS_TICKET_LINKS")

    def test_44_synthetic_confirmed_links_replay_without_mutation(self):
        # Synthetic fixtures, not an export or qualification of Debian's 44 rows.
        fixtures=[]
        for n in range(44):
            a=self.confirmed()
            a["external_glpi_observation"]["ticket_id"]=156+n
            a["database"]["glpi_links"][0]["glpi_ticket_id"]=156+n
            a["database"]["itsm_xref"][0]["ticket_id"]=156+n
            fixtures.append(a)
        before=deepcopy(fixtures)
        for a in fixtures:
            first=m.diagnose(a)
            self.assertEqual(first["verdict"],"PASS")
            self.assertEqual(m.diagnose(a),first)
        self.assertEqual(fixtures,before)

if __name__=="__main__":
    unittest.main()
