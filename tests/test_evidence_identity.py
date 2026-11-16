import datetime
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from shared.evidence_identity import canonical_evidence, evidence_digest, normalize_observed_at

class EvidenceIdentityTests(unittest.TestCase):
    def observation(self,**overrides):
        base=dict(source='monitoring',external_id='evt-1',
                  observed_at='2026-10-20T06:00:00Z',claim='Path degraded',
                  confidence=0.9,provenance={'run_id':'RUN-1','synthetic':True},
                  payload={'active_paths':1,'total_paths':4})
        base.update(overrides)
        return canonical_evidence(**base)

    def test_same_observation_replay_is_stable(self):
        a=self.observation()
        b=self.observation(observed_at='2026-10-20T08:00:00+02:00')
        self.assertEqual(a,b)
        self.assertEqual(evidence_digest(a),evidence_digest(b))

    def test_reusing_same_payload_for_other_run_is_distinct(self):
        a=self.observation()
        b=self.observation(provenance={'run_id':'RUN-2','synthetic':True})
        self.assertNotEqual(evidence_digest(a),evidence_digest(b))

    def test_claim_source_or_external_identity_affects_digest(self):
        original=evidence_digest(self.observation())
        for variation in (dict(source='other'),dict(external_id='evt-2'),
                          dict(claim='Paths healthy')):
            self.assertNotEqual(original,evidence_digest(self.observation(**variation)))

    def test_missing_timezone_and_invalid_time_are_rejected(self):
        for value in ('2026-10-20T06:00:00','wrong',''):
            with self.subTest(value=value),self.assertRaises(ValueError):
                normalize_observed_at(value)

    def test_invalid_or_client_supplied_quality_rejected(self):
        with self.assertRaises(ValueError):
            self.observation(external_id='')
        with self.assertRaises(ValueError):
            self.observation(provenance={'_aiops_quality':{'status':'FRESH'}})

    def test_utc_timestamp_normalized(self):
        self.assertEqual(normalize_observed_at('2026-10-20T06:00:00Z'),
                         '2026-10-20T06:00:00.000000Z')

if __name__=='__main__': unittest.main()
