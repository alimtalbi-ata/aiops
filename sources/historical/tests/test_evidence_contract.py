import datetime
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from shared.evidence_contract import validate_evidence,analysis_quality_errors,contradictory_snapshots,critique_quality_errors
from shared.evidence_identity import canonical_evidence,evidence_digest

NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
FRESH=[{'evidence_id':'E1','observed_at':NOW,'payload':{'active_paths':1,'total_paths':4}},
       {'evidence_id':'E2','observed_at':NOW,'payload':{'p95_seconds':4.8,'slo_seconds':.8}}]
STALE=[{'evidence_id':'S1','observed_at':'2025-01-01T00:00:00Z',
        'payload':{'active_paths':4,'total_paths':4}}]
ANALYSIS={'severity':'P1','confidence':.9,'hypotheses':[{'supporting_evidence_ids':['E1']} ]}
CRITIQUE={'validated':True,'issues':[],'claim_checks':[{'supported':True,'supporting_evidence_ids':['E1']}]}

class EvidenceContractTests(unittest.TestCase):
    def test_reject_duplicate_identifiers(self):
        self.assertIn('duplicate_evidence_id:E1',validate_evidence(FRESH+[FRESH[0]]))

    def test_reject_client_supplied_freshness_result(self):
        self.assertTrue(validate_evidence([{'evidence_id':'E1','_aiops_quality':{'status':'FRESH'}}]))

    def test_reject_provenance_time_conflict(self):
        self.assertIn('conflicting_observed_at:0',validate_evidence([
            {'evidence_id':'E1','observed_at':NOW,
             'provenance':{'observed_at':'2025-01-01T00:00:00Z'}}]))

    def test_canonical_database_evidence_is_verified_before_model_use(self):
        envelope=canonical_evidence(
            source="ci-monitor",external_id="RUN-1:paths",
            observed_at=NOW,claim="SAN paths degraded",confidence=0.9,
            provenance={"run_id":"RUN-1","synthetic":True,
                        "identity_contract":"canonical-envelope-v1"},
            payload={"active_paths":1,"total_paths":4})
        valid={"evidence_id":"E-VERIFIED",**envelope,
               "payload_hash":evidence_digest(envelope)}
        self.assertEqual(validate_evidence([valid]),[])
        corrupt={**valid,"claim":"SAN paths healthy"}
        self.assertIn("canonical_evidence_digest_mismatch:0",
                      validate_evidence([corrupt]))

    def test_canonical_claim_without_digest_is_not_trusted(self):
        envelope=canonical_evidence(
            source="ci-monitor",external_id="RUN-1:paths",
            observed_at=NOW,claim="synthetic observation",confidence=0.5,
            provenance={"synthetic":True,"identity_contract":"canonical-envelope-v1"},
            payload={"active_paths":1})
        value={"evidence_id":"E-UNVERIFIED",**envelope}
        self.assertIn("canonical_evidence_digest_mismatch:0",validate_evidence([value]))

    def test_current_p1_requires_fresh_citations(self):
        value=dict(ANALYSIS,hypotheses=[{'supporting_evidence_ids':['S1']}])
        self.assertIn('current_severity_not_grounded_in_fresh_evidence',
                      analysis_quality_errors(value,STALE))

    def test_fresh_grounding_satisfies_guard(self):
        self.assertEqual(analysis_quality_errors(ANALYSIS,FRESH),[])

    def test_same_evidence_cannot_support_and_contradict(self):
        value=dict(ANALYSIS,hypotheses=[{'supporting_evidence_ids':['E1'],'contradicting_evidence_ids':['E1']}])
        self.assertIn('hypothesis_cites_same_evidence_as_support_and_contradiction',
                      analysis_quality_errors(value,FRESH))

    def test_divergent_historical_snapshot_requires_challenge(self):
        self.assertTrue(contradictory_snapshots(FRESH+STALE))
        self.assertIn('divergent_snapshots_not_challenged',
                      critique_quality_errors(CRITIQUE,ANALYSIS,FRESH+STALE))

    def test_critic_with_fresh_evidence_and_no_conflict(self):
        self.assertEqual(critique_quality_errors(CRITIQUE,ANALYSIS,FRESH),[])

    def test_critic_cannot_validate_stale_only_claim(self):
        a=dict(ANALYSIS,hypotheses=[{'supporting_evidence_ids':['S1']}])
        c=dict(CRITIQUE,claim_checks=[{'supported':True,'supporting_evidence_ids':['S1']}])
        issues=critique_quality_errors(c,a,STALE)
        self.assertIn('no_fresh_evidence_for_current_claims',issues)

if __name__=='__main__': unittest.main()
