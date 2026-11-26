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
            ids=[]
            for phase,value in (("baseline",40),("incident",160)):
                sample=requests.post("http://127.0.0.1:1815/api/evidence",json={"source":"ci-lab-"+phase,"claim":"synthetic latency sample","confidence":0.5,"provenance":{"run_id":"RUN-CI-CONTEXT","synthetic":True},"payload":{"metric":"latency_ms","phase":phase,"value":value}},timeout=5)
                sample.raise_for_status()
                ids.append(sample.json()["evidence_id"])
            result=context(1814,1815,"RUN-CI-CONTEXT","NODE-CI-ROOT")
            self.assertEqual(result["diagnosis"]["evidence_ids"],ids)
            self.assertEqual(result["diagnosis"]["preview"]["conditional_reduction_ms"],120)
            self.assertEqual({x["node_id"] for x in result["affected"]},{"NODE-CI-ROOT","NODE-CI-CHILD"})
            self.assertIn(response.json()["evidence_id"],[e["evidence_id"] for e in result["evidence"]])
            self.assertEqual(result["rca"],"UNKNOWN")
            self.assertEqual(result["policy"],"DENY")
            with server(core_config=(1810,os.environ["AIOPS_INTERNAL_TOKEN"],"RUN-CI-CONTEXT"),
                        context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-CONTEXT"),policy_port=1813,mattermost_config=('ci-chatops-token-'+'x'*32,'ci-lab')) as http:
                thread=threading.Thread(target=http.serve_forever,daemon=True)
                thread.start()
                try:
                    url="http://127.0.0.1:%d/api/v1/incident-context" % http.server_port
                    response=requests.get(url,timeout=20)
                    response.raise_for_status()
                    body=response.json()
                    self.assertEqual(body["core"]["run"]["incident_id"],"INC-CI-CONTEXT")
                    self.assertEqual(body["context"],result)
                    self.assertEqual(body["copilot"]["sources"],result["evidence"])
                    self.assertIsNone(body["copilot"]["confidence"])
                    glpi_origin="http://127.0.0.1:%d" % http.server_port
                    glpi_url=glpi_origin+"/api/v1/glpi/preview"
                    ticket={"id":1,"synthetic":True,"run_id":"RUN-CI-CONTEXT"}
                    followup={"id":2,"items_id":1,"itemtype":"Ticket","content":"@copilot incident"}
                    def glpi(t):
                        return requests.post(glpi_url,json={"ticket":t,"followup":followup},headers={"Origin":glpi_origin},timeout=20)
                    receipt=glpi(ticket)
                    receipt.raise_for_status()
                    self.assertFalse(receipt.json()["posted"])
                    self.assertEqual(receipt.json()["input"]["is_private"],1)
                    self.assertIn(result["evidence"][0]["payload_hash"],receipt.json()["input"]["content"])
                    self.assertEqual(glpi(dict(ticket,synthetic=False)).status_code,503)
                    self.assertEqual(glpi(dict(ticket,run_id="wrong")).status_code,503)
                    chat_url="http://127.0.0.1:%d/api/v1/mattermost/command" % http.server_port
                    form={"token":"ci-chatops-token-"+"x"*32,"channel_id":"ci-lab","command":"/aiops","text":"incident"}
                    chat=requests.post(chat_url,data=form,timeout=20)
                    chat.raise_for_status()
                    self.assertEqual(chat.json()["response_type"],"ephemeral")
                    for value in ("INC-CI-CONTEXT","RUN-CI-CONTEXT","Root cause UNKNOWN","DENY",result["evidence"][0]["payload_hash"]):
                        self.assertIn(value,chat.json()["text"])
                    self.assertEqual(requests.post(chat_url,data=dict(form,token="wrong"),timeout=20).status_code,403)
                    self.assertEqual(requests.post(chat_url,data=dict(form,channel_id="wrong"),timeout=20).status_code,403)
                    blocked=requests.post(chat_url,data=dict(form,text="execute"),timeout=20)
                    blocked.raise_for_status()
                    self.assertIn("DENY",blocked.json()["text"])
                    from playwright.sync_api import sync_playwright, expect
                    with sync_playwright() as pw:
                        browser=pw.chromium.launch(headless=True)
                        try:
                            page=browser.new_page()
                            page.goto("http://127.0.0.1:%d/" % http.server_port)
                            page.locator("#load-context").click()
                            for value in ("INC-CI-CONTEXT","RUN-CI-CONTEXT","NODE-CI-CHILD",result["evidence"][0]["evidence_id"],"RCA: UNKNOWN","Policy: DENY","Conditional reduction: 120 ms","Copilot: Incident INC-CI-CONTEXT","Source: "):
                                expect(page.locator("#context-result")).to_contain_text(value)
                            # #833: assert the actual HTTP Analyst/Critic projection in Chromium.
                            analysis=body["copilot"]["analysis"]
                            criticism=body["copilot"]["criticism"]
                            self.assertEqual(analysis["hypothesis"],"INCIDENT_OBSERVED")
                            self.assertEqual(set(analysis["evidence_ids"]),{e["evidence_id"] for e in result["evidence"]})
                            self.assertTrue(criticism["evidence_supported"])
                            self.assertFalse(criticism["causality_established"])
                            for value in ("Analyst: "+analysis["hypothesis"],
                                          "Critic evidence: SUPPORTED",
                                          "Causality: NOT ESTABLISHED",
                                          "Critic operational decision: DENY"):
                                expect(page.locator("#context-result")).to_contain_text(value)
                            # Corrupt only the browser response, not the backend or database.
                            def unbound_evidence(route):
                                upstream=route.fetch()
                                projection=upstream.json()
                                projection["copilot"]["analysis"]["evidence_ids"]=["UNBOUND-CI-EVIDENCE"]
                                route.fulfill(response=upstream,json=projection)
                            page.route(url,unbound_evidence)
                            try:
                                page.locator("#load-context").click()
                                expect(page.locator("#context-result")).to_contain_text("UNKNOWN / DENY")
                                expect(page.locator("#context-result")).not_to_contain_text("Critic evidence: SUPPORTED")
                            finally:
                                page.unroute(url,unbound_evidence)
                            page.locator("#load-context").click()
                            expect(page.locator("#context-result")).to_contain_text("Critic evidence: SUPPORTED")
                            page.locator("#context-sim").click()
                            expect(page.locator("#context-result")).to_contain_text("Policy decision: SIMULATE")
                            expect(page.locator("#context-result")).to_contain_text("Host execution: NONE")
                            page.locator("#hitl-request").click()
                            expect(page.locator("#hitl-result")).to_contain_text("HUMAN_APPROVAL")
                            page.locator("#hitl-approve").click()
                            expect(page.locator("#hitl-result")).to_contain_text("SIMULATE_ONLY")
                            page.locator("#hitl-request").click()
                            expect(page.locator("#hitl-result")).to_contain_text("HUMAN_APPROVAL")
                            page.locator("#hitl-deny").click()
                            expect(page.locator("#hitl-result")).to_contain_text("DENY")
                            origin="http://127.0.0.1:%d" % http.server_port
                            req=requests.post(origin+"/api/v1/hitl/request",json={},headers={"Origin":origin},timeout=10)
                            req.raise_for_status()
                            payload={"request_id":req.json()["request_id"],"approved":True}
                            for decision in ("SIMULATE_ONLY","DENY"):
                                receipt=requests.post(origin+"/api/v1/hitl/decide",json=payload,headers={"Origin":origin},timeout=10)
                                receipt.raise_for_status()
                                self.assertEqual(receipt.json()["decision"],decision)
                                self.assertFalse(receipt.json()["executed_on_host"])
                            self.assertEqual(requests.post(origin+"/api/v1/hitl/request",json={},headers={"Origin":"https://invalid.example"},timeout=10).status_code,503)
                            with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                                self.assertEqual(db.execute("select status from aiops.runs where run_id='RUN-CI-CONTEXT'").fetchone()[0],"CREATED")
                                self.assertEqual(db.execute("select count(*) from aiops.evidence where provenance->>'run_id'='RUN-CI-CONTEXT'").fetchone()[0],3)
                            http.context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-WRONG")
                            page.locator("#load-context").click()
                            expect(page.locator("#context-result")).to_contain_text("UNKNOWN / DENY")
                        finally:
                            browser.close()
                    http.context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-WRONG")
                    self.assertEqual(requests.get(url,timeout=20).status_code,503)
                    http.context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-CONTEXT")
                    origin="http://127.0.0.1:%d" % http.server_port
                    a=dict(id="m1",kind="metric",source="monitor",resource="NODE-CI-ROOT",severity="critical",tenant="synthetic-demo",synthetic=True)
                    batch=[dict(a,observation={"metric":"latency_ms","phase":"baseline","value":40}),
                           dict(a,id="m2",observation={"metric":"latency_ms","phase":"incident","value":160})]
                    def persist_http():
                        response=requests.post(origin+"/api/v1/ingest/persist",json=batch,headers={"Origin":origin},timeout=20)
                        response.raise_for_status()
                        return response.json()
                    dynamic_url=origin+"/api/v1/ingest/create"
                    try:
                        first=requests.post(dynamic_url,json=batch,headers={"Origin":origin},timeout=20)
                        first.raise_for_status()
                        second=requests.post(dynamic_url,json=batch,headers={"Origin":origin},timeout=20)
                        second.raise_for_status()
                        self.assertEqual(first.json(),second.json())
                        dynamic=first.json()["core"]["run"]
                        self.assertEqual(dynamic["mode"],"DEMO")
                        self.assertEqual(len(first.json()["stored_evidence"]),2)
                        context_url=origin+"/api/v1/incident-context/dynamic?run_id="+dynamic["run_id"]
                        projection=requests.get(context_url,timeout=20)
                        projection.raise_for_status()
                        details=projection.json()
                        self.assertEqual(details["core"]["run"],dynamic)
                        self.assertEqual(details["binding"],"VERIFIED_DYNAMIC_LAB_NODE")
                        self.assertCountEqual(details["context"]["evidence"],first.json()["stored_evidence"])
                        diagnosis=details["context"]["diagnosis"]
                        self.assertEqual(diagnosis["hypothesis"],"LATENCY_REGRESSION_OBSERVED")
                        self.assertEqual(diagnosis["preview"]["conditional_reduction_ms"],120)
                        self.assertCountEqual(diagnosis["evidence_ids"],[e["evidence_id"] for e in first.json()["stored_evidence"]])
                        self.assertIsNone(diagnosis["confidence"])
                        self.assertFalse(diagnosis["executed_on_host"])
                        self.assertEqual(details["copilot"]["root_cause"],"UNKNOWN")
                        self.assertEqual(details["copilot"]["operational_decision"],"DENY")
                        self.assertIn("NODE-CI-CHILD",[x["node_id"] for x in details["context"]["affected"]])
                        decision=requests.get(context_url+"&decision=simulate",timeout=20)
                        decision.raise_for_status()
                        simulation=decision.json()["simulation"]
                        self.assertEqual(decision.json()["core"]["run"],dynamic)
                        self.assertEqual(simulation["policy_decision"],"SIMULATE")
                        self.assertTrue(simulation["simulation_only"])
                        self.assertEqual(simulation["operational_decision"],"DENY")
                        self.assertFalse(simulation["executed_on_host"])
                        self.assertFalse(simulation["production_authorized"])
                        self.assertEqual(requests.get(context_url+"&decision=execute",timeout=20).status_code,503)
                        def dynamic_hitl(action,data):
                            return requests.post(origin+"/api/v1/hitl/dynamic/"+action,json=data,headers={"Origin":origin},timeout=20)
                        approval=dynamic_hitl("request",{"run_id":dynamic["run_id"]})
                        approval.raise_for_status()
                        self.assertEqual(approval.json()["decision"],"HUMAN_APPROVAL")
                        self.assertEqual(approval.json()["run_id"],dynamic["run_id"])
                        decision_payload={"run_id":dynamic["run_id"],"request_id":approval.json()["request_id"],"approved":True}
                        for expected_decision in ("SIMULATE_ONLY","DENY"):
                            receipt=dynamic_hitl("decide",decision_payload)
                            receipt.raise_for_status()
                            self.assertEqual(receipt.json()["decision"],expected_decision)
                            self.assertFalse(receipt.json()["executed_on_host"])
                            self.assertFalse(receipt.json()["production_authorized"])
                            self.assertEqual(receipt.json()["operational_decision"],"DENY")
                        self.assertEqual(dynamic_hitl("request",{"run_id":"RUN-CI-CONTEXT"}).status_code,503)
                        self.assertEqual(requests.post(origin+"/api/v1/hitl/dynamic/request",json={"run_id":dynamic["run_id"]},headers={"Origin":"https://invalid.example"},timeout=20).status_code,503)
                        self.assertEqual(requests.get(context_url.replace(dynamic["run_id"],"RUN-CI-CONTEXT"),timeout=20).status_code,503)
                        http.context_config=(1814,1815,"NODE-CI-CHILD","INC-CI-CONTEXT")
                        try:
                            self.assertEqual(requests.get(context_url,timeout=20).status_code,503)
                        finally:
                            http.context_config=(1814,1815,"NODE-CI-ROOT","INC-CI-CONTEXT")
                        with sync_playwright() as pw:
                            browser=pw.chromium.launch(headless=True)
                            try:
                                page=browser.new_page()
                                page.goto(origin+"/")
                                page.locator("#create-dynamic").click()
                                for value in ("Incident: INC-","Run: RUN-","Mode: DEMO","RCA: UNKNOWN","Policy: DENY","Evidence: "):
                                    expect(page.locator("#dynamic-result")).to_contain_text(value,timeout=20000)
                                page.locator("#simulate-dynamic-context").click()
                                for value in ("Verified dynamic lab binding","Policy decision: SIMULATE","Host execution: NONE","Conditional reduction: 120 ms"):
                                    expect(page.locator("#context-result")).to_contain_text(value,timeout=20000)
                                page.locator("#dynamic-hitl-request").click()
                                expect(page.locator("#dynamic-hitl-result")).to_contain_text("HUMAN_APPROVAL",timeout=20000)
                                page.locator("#dynamic-hitl-approve").click()
                                expect(page.locator("#dynamic-hitl-result")).to_contain_text("SIMULATE_ONLY",timeout=20000)
                                page.locator("#dynamic-hitl-request").click()
                                expect(page.locator("#dynamic-hitl-result")).to_contain_text("HUMAN_APPROVAL",timeout=20000)
                                page.locator("#dynamic-hitl-deny").click()
                                expect(page.locator("#dynamic-hitl-result")).to_have_text(__import__("re").compile(r"^DENY — RUN-"),timeout=20000)
                                previous=page.locator("#dynamic-result").inner_text()
                                page.locator("#create-dynamic").click()
                                expect(page.locator("#dynamic-result")).to_have_text(previous,timeout=20000)
                            finally:
                                browser.close()
                        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                            self.assertEqual(db.execute("select count(*) from aiops.evidence where provenance->>'run_id'=%s",(dynamic["run_id"],)).fetchone()[0],2)
                            self.assertEqual(db.execute("select status from aiops.runs where run_id=%s",(dynamic["run_id"],)).fetchone()[0],"CREATED")
                    finally:
                        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                            db.execute("delete from aiops.evidence where provenance->>'run_id' in (select run_id from aiops.runs where scenario_id='CI-INGEST')")
                            db.execute("delete from aiops.run_events where run_id in (select run_id from aiops.runs where scenario_id='CI-INGEST')")
                            db.execute("delete from aiops.run_stage_state where run_id in (select run_id from aiops.runs where scenario_id='CI-INGEST')")
                            db.execute("delete from aiops.runs where scenario_id='CI-INGEST'")
                            db.execute("delete from aiops.incidents where external_id like 'CI-INGEST-%'")
                    stored=persist_http()
                    self.assertEqual(len(stored["stored_evidence"]),2)
                    self.assertEqual(persist_http()["stored_evidence"],stored["stored_evidence"])
                    with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                        self.assertEqual(db.execute("select count(*) from aiops.evidence where provenance->>'run_id'='RUN-CI-CONTEXT'").fetchone()[0],5)
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
