import unittest
from datetime import datetime, timezone
from demo.noc_portal_integration import validate_noc_runtime_snapshot
def data():
    return {"schema":"aiops-noc-runtime-readmodel-v1",
            "provenance":"RUNTIME_READMODEL","runtime_authenticated":True,
            "live_remediation_authorized":False,"run_id":"RUN-001","incident_id":"INC-001",
            "observed_at":"2026-10-20T12:00:00Z",
            "steps":[{"name":"detect","state":"WARN"}]}
class PortalNocContractTests(unittest.TestCase):
    def test_verified_read_model_accepted(self):self.assertEqual(validate_noc_runtime_snapshot(data(),now_utc="2026-10-20T12:01:00Z")["run_id"],"RUN-001")
    def test_synthetic_not_promoted(self):
        d=data();d["provenance"]="SYNTHETIC"
        with self.assertRaises(ValueError):validate_noc_runtime_snapshot(d)
    def test_no_source_fails_closed(self):
        with self.assertRaises(ValueError):validate_noc_runtime_snapshot({})
    def test_action_claim_rejected(self):
        d=data();d["live_remediation_authorized"]=True
        with self.assertRaises(ValueError):validate_noc_runtime_snapshot(d)
    def test_unknown_step_rejected(self):
        d=data();d["steps"][0]["state"]="REMEDIATED"
        with self.assertRaisesRegex(ValueError,"invalid timeline step"):
            validate_noc_runtime_snapshot(d,now_utc="2026-10-20T12:01:00Z")
    def test_stale_live_snapshot_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"stale or future"):
            validate_noc_runtime_snapshot(data(),now_utc="2026-10-20T12:06:00Z")
    def test_future_snapshot_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"stale or future"):
            validate_noc_runtime_snapshot(data(),now_utc="2026-10-20T11:59:59Z")
    def test_exact_freshness_boundary(self):
        self.assertEqual(validate_noc_runtime_snapshot(
            data(),now_utc="2026-10-20T12:05:00Z")["incident_id"],"INC-001")
    def test_invalid_freshness_policy_rejected(self):
        for invalid in (0,True,3601,"300"):
            with self.subTest(invalid=invalid),self.assertRaisesRegex(ValueError,"freshness policy"):
                validate_noc_runtime_snapshot(data(),max_age_seconds=invalid)
    def test_invalid_injected_clock_rejected(self):
        for invalid in ("2026-10-20T12:01:00+02:00","not-a-clock",123):
            with self.subTest(invalid=invalid),self.assertRaisesRegex(ValueError,"NOC clock"):
                validate_noc_runtime_snapshot(data(),now_utc=invalid)
if __name__=="__main__":unittest.main()
