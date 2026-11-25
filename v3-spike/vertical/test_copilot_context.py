import unittest
from copilot_context import answer

class CopilotTest(unittest.TestCase):
    def test_context(self):
        core={"production_authorized":False,"run":{"run_id":"RUN-CI-X","incident_id":"INC-CI-X"}}
        ctx={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":"RUN-CI-X","policy":"DENY","affected":[{"node_id":"NODE-CI-X"}],"evidence":[{"evidence_id":"E1","payload_hash":"a"*64}]}
        result=answer(core,ctx)
        self.assertEqual(result["sources"],ctx["evidence"])
        self.assertIsNone(result["confidence"])
        self.assertEqual(result["root_cause"],"UNKNOWN")
        self.assertEqual(result["operational_decision"],"DENY")
        with self.assertRaises(ValueError):
            answer(core,dict(ctx,run_id="RUN-CI-Y"))
        with self.assertRaises(ValueError):
            answer(core,dict(ctx,production_authorized=True))
