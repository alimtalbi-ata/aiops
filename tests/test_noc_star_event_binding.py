import unittest
import hashlib
import json
from demo.noc_star_event_binding import bind_synthetic_star_events
from demo.noc_star_cue_map import CUES
def index():
    names=("unified","synthetic","checkmk-export")
    return {"schema":"aiops-noc-evidence-index-v1","counts":{"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0},
            "runtime_authenticated":False,"live_remediation_authorized":False,
            "entries":[{"id":"noc-offline-"+n,"file":n+".png","sha256":"a"*64,"size_bytes":123,"class":"OFFLINE_TEST",
                        "source":"LOCAL_OFFLINE_BROWSER_RENDER","runtime_authenticated":False,
                        "promotable_to_runtime":False} for n in names]}
def events():
    return [{"cue":cue,"run_id":"RUN-DEMO","incident_id":"INC-DEMO","event_id":"EV-"+str(i),
             "source_type":"SYNTHETIC","payload":{"step":i}} for i,cue in enumerate(CUES)]
class SyntheticStarBindingTests(unittest.TestCase):
    def test_nine_events_bound_without_runtime_claim(self):
        result=bind_synthetic_star_events(index(),events())
        self.assertEqual(len(result["events"]),9)
        self.assertEqual(result["verified_runtime_event_links"],0)
        self.assertEqual(len(result["captures"]),3)
        self.assertTrue(all(len(x["event_sha256"])==64 for x in result["events"]))
    def test_mixed_incidents_rejected(self):
        rows=events();rows[3]["incident_id"]="INC-OTHER"
        with self.assertRaises(ValueError):bind_synthetic_star_events(index(),rows)
    def test_forged_source_rejected(self):
        rows=events();rows[1]["source_type"]="REAL"
        with self.assertRaises(ValueError):bind_synthetic_star_events(index(),rows)
    def test_reordered_cues_rejected(self):
        rows=events();rows[1],rows[2]=rows[2],rows[1]
        with self.assertRaises(ValueError):bind_synthetic_star_events(index(),rows)
    def test_binding_hash_covers_exact_event_and_capture_association(self):
        output=bind_synthetic_star_events(index(),events())
        for capture in output["captures"]:
            association={"run_id":output["run_id"],"incident_id":output["incident_id"],
                         "capture_file":capture["file"],"capture_sha256":capture["sha256"],
                         "illustrative_cues":capture["illustrative_cues"],
                         "synthetic_events":capture["synthetic_event_hashes"]}
            canonical=json.dumps(association,sort_keys=True,separators=(",",":"),
                                 ensure_ascii=False,allow_nan=False).encode("utf-8")
            self.assertEqual(capture["binding_sha256"],hashlib.sha256(canonical).hexdigest())
            self.assertEqual(capture["synthetic_event_ids"],
                             [e["event_id"] for e in capture["synthetic_event_hashes"]])
            self.assertFalse(capture["runtime_authenticated"])
        self.assertEqual(output,bind_synthetic_star_events(index(),events()))

    def test_event_payload_change_invalidates_only_affected_capture_bindings(self):
        baseline={c["file"]:c["binding_sha256"] for c in bind_synthetic_star_events(index(),events())["captures"]}
        altered=events();altered[0]["payload"]["step"]=999
        changed={c["file"]:c["binding_sha256"] for c in bind_synthetic_star_events(index(),altered)["captures"]}
        self.assertNotEqual(baseline["unified.png"],changed["unified.png"])
        self.assertNotEqual(baseline["checkmk-export.png"],changed["checkmk-export.png"])
        self.assertEqual(baseline["synthetic.png"],changed["synthetic.png"])

    def test_capture_digest_change_invalidates_only_its_binding(self):
        baseline={c["file"]:c["binding_sha256"] for c in bind_synthetic_star_events(index(),events())["captures"]}
        altered=index();altered["entries"][0]["sha256"]="b"*64
        changed={c["file"]:c["binding_sha256"] for c in bind_synthetic_star_events(altered,events())["captures"]}
        self.assertNotEqual(baseline["unified.png"],changed["unified.png"])
        self.assertEqual(baseline["synthetic.png"],changed["synthetic.png"])
        self.assertEqual(baseline["checkmk-export.png"],changed["checkmk-export.png"])

    def test_non_ascii_identifier_rejected_fail_closed(self):
        altered=events();altered[0]["run_id"]="RUN-Δ"
        with self.assertRaises(ValueError):
            bind_synthetic_star_events(index(),altered)

    def test_oversized_event_rejected_before_binding(self):
        altered=events();altered[0]["payload"]["oversized"]="X"*65_536
        with self.assertRaisesRegex(ValueError,"bounded hash input"):
            bind_synthetic_star_events(index(),altered)

if __name__=="__main__":unittest.main()
