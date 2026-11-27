"""Exact-source countertests for duplicated and conflicting Evidence projections."""
import hashlib
import json
import unittest
from unittest.mock import patch
from lab_context import context
from analyst_critic import analyze, critique
from evidence_retrieval import retrieve

RUN="RUN-0123456789ABCDEF"
INC="INC-CI-INGEST-"+"a"*32
ROOT="NODE-CI-ROOT"

def evidence(eid,phase,value):
    payload={"run_id":RUN,"incident_id":INC,"resource":ROOT,
             "signal":{"source":"metric:lab","observation":{"metric":"latency_ms","phase":phase,"value":value}}}
    return {"evidence_id":eid,"source":"v3-synthetic-ingestion","provenance":{"run_id":RUN,"synthetic":True},
            "payload":payload,"payload_hash":hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()}

def projection(items):
    with patch("lab_context.get",return_value={"root":ROOT,"affected":[{"node_id":ROOT,"depth":0}]}):
        return context(18101,18102,RUN,ROOT,dynamic_incident=INC,include_signals=True,evidence_snapshot={"items":items})

class EvidenceIntegrityTest(unittest.TestCase):
    def test_distinct_dynamic_evidence_supports_observation_not_causality(self):
        baseline=evidence("E1","baseline",10)
        incident=evidence("E2","incident",100)
        verified=projection([baseline,incident])
        self.assertEqual(len(verified["evidence"]),2)
        self.assertEqual(len(verified["verified_signals"]),2)
        self.assertEqual(verified["diagnosis"]["hypothesis"],"LATENCY_REGRESSION_OBSERVED")
        analysis=analyze(verified)
        self.assertTrue(critique(analysis,verified)["evidence_supported"])
        self.assertEqual(analysis["evidence_ids"],["E1","E2"])
        self.assertEqual(retrieve({"run":{"run_id":RUN,"incident_id":INC,"mode":"DEMO"},"production_authorized":False},verified)["match_count"],2)
        self.assertEqual(analysis["root_cause"],"UNKNOWN")

    def test_dynamic_duplicate_identity_is_rejected(self):
        baseline=evidence("E1","baseline",10)
        incident=evidence("E2","incident",100)
        for items in ([baseline,baseline,incident],[baseline,incident,incident],
                      [baseline,baseline,incident,incident]):
            with self.subTest(items=items):
                with self.assertRaisesRegex(ValueError,"duplicate dynamic evidence identity"):
                    projection(items)

    def test_legacy_identical_duplicate_is_not_an_independent_observation(self):
        run="RUN-CI-EVIDENCE"
        def legacy(eid,phase,value):
            payload={"metric":"latency_ms","phase":phase,"value":value}
            return {"evidence_id":eid,"source":"legacy-fixture",
                    "provenance":{"run_id":run,"synthetic":True},"payload":payload,
                    "payload_hash":hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
        baseline=legacy("E1","baseline",10)
        incident=legacy("E2","incident",100)
        with patch("lab_context.get",return_value={"root":ROOT,"affected":[{"node_id":ROOT,"depth":0}]}):
            one=context(18101,18102,run,ROOT,evidence_snapshot={"items":[baseline,incident]})
            repeated=context(18101,18102,run,ROOT,evidence_snapshot={"items":[baseline,baseline,incident,incident]})
            self.assertEqual(one,repeated)
            self.assertEqual(len(repeated["evidence"]),2)
            self.assertEqual(repeated["diagnosis"]["hypothesis"],"LATENCY_REGRESSION_OBSERVED")
            with self.assertRaisesRegex(ValueError,"conflicting evidence identity"):
                context(18101,18102,run,ROOT,evidence_snapshot={"items":[baseline,legacy("E1","baseline",20),incident]})

    def test_identity_conflict_and_invalid_references(self):
        baseline=evidence("E1","baseline",10)
        incident=evidence("E2","incident",100)
        conflict=evidence("E1","baseline",20) # both hashes valid, same id
        for items in ([baseline,conflict,incident],[baseline,dict(baseline,source="other")],
                      [dict(baseline,evidence_id="")],[dict(baseline,evidence_id=None)],
                      [dict(baseline,evidence_id=42)],[dict(baseline,payload_hash="b"*64)],
                      [baseline]*21):
            with self.subTest(items=items):
                with self.assertRaises(ValueError): projection(items)

    def test_empty_or_foreign_dynamic_snapshot(self):
        baseline=evidence("E1","baseline",10)
        with self.assertRaises(ValueError): projection([])
        with self.assertRaises(ValueError): projection([dict(baseline,provenance={"run_id":"RUN-FFFFFFFFFFFFFFFF","synthetic":True})])

if __name__=="__main__": unittest.main()
