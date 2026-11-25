import os
import sys
import unittest
import threading
from psycopg.types.json import Jsonb
from pathlib import Path
import psycopg
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"v3-spike"/"vertical"))
from lab_context import context
from http_demo import server

class LabContextReal(unittest.TestCase):
    def test_real_context(self):
        with psycopg.connect(os.environ["DATABASE_URL"]) as c:
            c.execute("insert into aiops.incidents(incident_id,external_id,title,severity,state,opened_at,source,synthetic,payload) values ('INC-CI-CONTEXT','CI-CONTEXT','CI context','P1','OPEN',now(),'ci',true,%s)",(Jsonb({}),))
            c.execute("insert into aiops.runs(run_id,incident_id,mode,scenario_id,status,idempotency_key) values ('RUN-CI-CONTEXT','INC-CI-CONTEXT','DEMO','CI-CONTEXT','CREATED','ci-context')")
            c.execute("insert into aiops.twin_nodes(node_id,type,name) values ('NODE-CI-ROOT','service','CI root'),('NODE-CI-CHILD','service','CI child')")
            c.execute("insert into aiops.twin_edges(edge_id,source_id,target_id,relation_type,confidence) values ('EDGE-CI-01','NODE-CI-ROOT','NODE-CI-CHILD','depends',1)")
        try:
            response=requests.post("http://127.0.0.1:1815/api/evidence",json={"source":"ci-lab","claim":"synthetic observation","confidence":0.5,"provenance":{"run_id":"RUN-CI-CONTEXT","synthetic":True},"payload":{"metric":"latency","value":42}},timeout=5)
            response.raise_for_status()
            result=context(1814,1815,"RUN-CI-CONTEXT","NODE-CI-ROOT")
            self.assertEqual({x["node_id"] for x in result["affected"]},{"NODE-CI-ROOT","NODE-CI-CHILD"})
            self.assertEqual(result["evidence"][0]["evidence_id"],response.json()["evidence_id"])
            self.assertEqual(result["rca"],"UNKNOWN")
            self.assertEqual(result["policy"],"DENY")
            with server(core_config=(1810,os.environ["AIOPS_INTERNAL_TOKEN"],"RUN-CI-CONTEXT"),
                        context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-CONTEXT"),policy_port=1813) as http:
                thread=threading.Thread(target=http.serve_forever,daemon=True)
                thread.start()
                try:
                    url="http://127.0.0.1:%d/api/v1/incident-context" % http.server_port
                    response=requests.get(url,timeout=20)
                    response.raise_for_status()
                    body=response.json()
                    self.assertEqual(body["core"]["run"]["incident_id"],"INC-CI-CONTEXT")
                    self.assertEqual(body["context"],result)
                    from playwright.sync_api import sync_playwright, expect
                    with sync_playwright() as pw:
                        browser=pw.chromium.launch(headless=True)
                        try:
                            page=browser.new_page()
                            page.goto("http://127.0.0.1:%d/" % http.server_port)
                            page.locator("#load-context").click()
                            for value in ("INC-CI-CONTEXT","RUN-CI-CONTEXT","NODE-CI-CHILD",result["evidence"][0]["evidence_id"],"RCA: UNKNOWN","Policy: DENY"):
                                expect(page.locator("#context-result")).to_contain_text(value)
                            page.locator("#context-sim").click()
                            expect(page.locator("#context-result")).to_contain_text("Policy decision: SIMULATE")
                            expect(page.locator("#context-result")).to_contain_text("Host execution: NONE")
                            with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                                self.assertEqual(db.execute("select status from aiops.runs where run_id='RUN-CI-CONTEXT'").fetchone()[0],"CREATED")
                                self.assertEqual(db.execute("select count(*) from aiops.evidence where provenance->>'run_id'='RUN-CI-CONTEXT'").fetchone()[0],1)
                            http.context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-WRONG")
                            page.locator("#load-context").click()
                            expect(page.locator("#context-result")).to_contain_text("UNKNOWN / DENY")
                        finally:
                            browser.close()
                    http.context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-WRONG")
                    self.assertEqual(requests.get(url,timeout=20).status_code,503)
                finally:
                    http.shutdown()
                    thread.join(5)
        finally:
            with psycopg.connect(os.environ["DATABASE_URL"]) as c:
                c.execute("delete from aiops.runs where run_id='RUN-CI-CONTEXT'")
                c.execute("delete from aiops.incidents where incident_id='INC-CI-CONTEXT'")
                c.execute("delete from aiops.evidence where provenance->>'run_id'='RUN-CI-CONTEXT'")
                c.execute("delete from aiops.twin_edges where edge_id='EDGE-CI-01'")
                c.execute("delete from aiops.twin_nodes where node_id in ('NODE-CI-ROOT','NODE-CI-CHILD')")
