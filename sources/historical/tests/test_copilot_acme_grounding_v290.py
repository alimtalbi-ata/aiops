import ast
import unittest
from pathlib import Path

source=(Path(__file__).resolve().parents[1]/"app/copilot/main.py").read_text()
tree=ast.parse(source)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="grounded_answer")
module=ast.Module(body=[node],type_ignores=[])
ns={}
exec(compile(ast.fix_missing_locations(module),"<grounded_answer>","exec"),ns)
ask=ns["grounded_answer"]

class ACMECopilotTests(unittest.TestCase):
    def test_unknown_run_does_not_fabricate(self):
        r=ask("Pourquoi incident ?","RUN-ABSENT",[],[],[])
        self.assertIn("UNKNOWN",r["answer"])
        self.assertEqual(r["scope"],"ACME")
    def test_stage_marker_not_diagnostic(self):
        data=ask("Quelles preuves ?","RUN-1",
          [{"run_id":"RUN-1","status":"BLOCKED","mode":"DEMO","incident_id":"INC-1"}],[],[],
          {"run":{"run_id":"RUN-1","status":"BLOCKED","mode":"DEMO","incident_id":"INC-1"},"events":[]},
          {},{"items":[{"provenance":{"record_type":"stage_marker"}}]})
        self.assertIn("non probant",data["answer"])
        self.assertEqual(data["actions_performed"],[])
    def test_no_glpi_ticket_invented(self):
        r=ask("Quel ticket GLPI ?",None,[],[{"incident_id":"INC-X"}],[])
        self.assertIn("aucun ticket ne sera inventé",r["answer"])
        self.assertIsNone(r["confidence"])
if __name__=="__main__":
    unittest.main()
