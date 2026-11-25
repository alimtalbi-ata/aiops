import unittest
from glpi_demo import preview
class GLPITest(unittest.TestCase):
    def test_preview(self):
        core={"production_authorized":False,"run":{"run_id":"RUN-CI-X","incident_id":"INC-CI-X"}}
        context={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":"RUN-CI-X","policy":"DENY","affected":[],"evidence":[{"evidence_id":"E1","payload_hash":"a"*64}]}
        ticket={"id":1,"synthetic":True,"run_id":"RUN-CI-X"}
        followup={"id":2,"items_id":1,"itemtype":"Ticket","content":"@copilot incident"}
        result=preview(ticket,followup,core,context)
        self.assertEqual(result,preview(ticket,followup,core,context))
        self.assertEqual(result["input"]["is_private"],1)
        self.assertFalse(result["posted"])
        self.assertIn("E1",result["input"]["content"])
        self.assertIn("UNKNOWN",result["input"]["content"])
        self.assertEqual(result["operational_decision"],"DENY")
        for invalid in (dict(ticket,synthetic=False),dict(ticket,run_id="other")):
            with self.assertRaises(ValueError): preview(invalid,followup,core,context)
        with self.assertRaises(ValueError): preview(ticket,dict(followup,items_id=3),core,context)
if __name__=="__main__": unittest.main()
