import unittest
from copy import deepcopy
from test_int07_offline_collector import CollectorTests
from portal.acme_runtime_context import digest
from portal.acme_runtime_workbench import render_collector_result

class RuntimeWorkbenchTests(unittest.TestCase):
    def test_actual_collector(self):
        fixture=CollectorTests()
        for case in ("nominal","authority","stale","snapshot","identity","critic","policy","receipt","terminal","live"):
            with self.subTest(case=case):
                f,e=fixture.fixture()
                if case=="authority": f.rows["core"]=None
                if case=="stale": e["prepared"]["observed_at"]="2026-11-18T08:00:00Z"
                if case=="snapshot": f.rows["core"]["snapshot_id"]="FOREIGN"
                if case=="identity": f.rows["core"]["content"]["tenant_id"]="FOREIGN"
                if case in ("critic","policy","live"):
                    role="manifest" if case=="live" else "independent"
                    key={"critic":"critic_decision","policy":"policy_decision","live":"runtime_attested"}[case]
                    e[role]["content"][key]=True if case=="live" else "DENY"
                    e[role]["content_sha256"]=digest(e[role]["content"])
                if case=="receipt": e["receipt"]=None
                if case=="terminal": e["terminal"]["content"]["version"]=1; e["terminal"]["content_sha256"]=digest(e["terminal"]["content"])
                result,_=fixture.invoke(f,e)
                html=render_collector_result(result)
                self.assertIn("PROD / LIVE : NO-GO",html)
                self.assertIn("UNBOUND",html)
                self.assertIn(result["reason"],html)
                self.assertNotIn("RESOLVED",html)
                self.assertEqual("CONTRACT_ONLY" in html,case=="nominal")
    def test_forged(self):
        for value in (None,{},{"qualification":"PASS","scope":"LIVE"},{"runtime_attested":True}):
            html=render_collector_result(value)
            self.assertNotIn("CONTRACT_ONLY",html)
            self.assertIn("NO-GO",html)
