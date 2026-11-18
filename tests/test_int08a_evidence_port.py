import unittest
from portal.acme_workbench_presentation import event_facts, evidence_catalog, render_offline_evidence

class EventDetailsTests(unittest.TestCase):
    def test_analyst_and_critic_details(self):
        event={"stage":"DGX_CRITIC","event_type":"CRITIC_COMPLETED",
               "status":"BLOCKED","decision":"HUMAN_APPROVAL",
               "evidence_ids":["E-1"],"confidence":.65,
               "payload":{"critique":{"validated":False,"final_recommendation":"HUMAN_APPROVAL",
                         "issues":[{"code":"CAUSAL_LEAP","description":"Not proven"}]}}}
        html=event_facts(event)
        for value in ("E-1","0.65","HUMAN_APPROVAL","CAUSAL_LEAP","Not proven"):
            self.assertIn(value,html)
    def test_error_and_html_escaped(self):
        html=event_facts({"stage":"DGX_ANALYST","event_type":"STAGE_FAILED",
                          "status":"FAILED","payload":{"error":"<script>alert(1)</script>",
                          "analysis":{"severity":"UNKNOWN","confidence":.2,
                          "hypotheses":[{"statement":"<img src=x>",
                                         "supporting_evidence_ids":["E1"]}]}}})
        self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("<script>",html)
        self.assertNotIn("<img",html)
        self.assertIn("UNKNOWN",html)
    def test_missing_details_not_fabricated(self):
        self.assertIn("Aucune donnée détaillée",event_facts({"stage":"NORMALIZE"}))

class EvidenceCatalogTests(unittest.TestCase):
    def test_provenance_source_and_timestamps(self):
        html=evidence_catalog([{"evidence_id":"EVD-1","source":"demo-observe",
          "claim":"FC errors increased","observed_at":"2026-10-21T12:00:00Z",
          "known_at":"2026-10-21T12:01:00Z","confidence":0.85,
          "payload_hash":"abcdef","provenance":{"synthetic":True}}])
        for value in ('id="proof-EVD-1"',"FC errors increased","demo-observe","abcdef","synthetic"):
            self.assertIn(value,html)
    def test_xss_and_missing_data(self):
        self.assertIn("Aucune preuve",evidence_catalog([]))
        html=evidence_catalog([{"evidence_id":"EVD-2","source":"<script>alert(1)</script>",
                                  "claim":"<img src=x>","provenance":{"unsafe":"<b>"}}])
        self.assertNotIn("<script>",html)
        self.assertNotIn("<img",html)
        self.assertIn("&lt;script&gt;",html)
    def test_stage_marker_is_not_diagnostic_proof(self):
        html=evidence_catalog([{"evidence_id":"EVD-MARK","source":"run:R1:normalize",
                "claim":"NORMALIZE completed","provenance":{"record_type":"stage_marker",
                "synthetic":True}}])
        self.assertIn("1 marqueur(s) d’exécution",html)
        self.assertIn("ne démontrent pas une dégradation SAN",html)
        self.assertIn("non probant pour le diagnostic",html)


class OfflineBoundaryTests(unittest.TestCase):
    def test_no_raw_payload_or_invented_times(self):
        rendered = render_offline_evidence([{"payload":{"secret":"never-display"}}], [{"evidence_id":"E-1","provenance":{"secret":"never-display"}}])
        self.assertNotIn("never-display", rendered)
        for value in ("observed_at", "known_at", "MISSING", "UNKNOWN", "NO-GO LIVE"):
            self.assertIn(value, rendered)
    def test_malformed(self):
        self.assertIn("UNKNOWN", evidence_catalog([{"evidence_id":[]}]))
        self.assertIn("Aucune donnée", event_facts(None))
