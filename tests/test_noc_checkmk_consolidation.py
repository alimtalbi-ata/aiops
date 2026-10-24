import unittest
from demo.noc_checkmk_consolidation import consolidate_checkmk_snapshot
H={"schema":"aiops-checkmk-offline-readonly-v1","provenance":"OPERATOR_EXPORT_UNVERIFIED","runtime_authenticated":False,"live_remediation_authorized":False,"captured_at":"2026-10-24T20:00:00Z","age_seconds":60.0,"hosts":{"brocade-fc01":{"state":"OK","output":"up"}}}
S={"schema":"aiops-checkmk-services-loopback-v1","provenance":"LOOPBACK_UNVERIFIED","runtime_authenticated":False,"live_remediation_authorized":False,"captured_at":"2026-10-24T20:00:00Z","age_seconds":60.0,"services":[{"host":"brocade-fc01","description":"FC port","state":"CRIT","output":"down"}]}
class ConsolidationTests(unittest.TestCase):
    def test_service_impact_promotes_host_overall_state(self):
        r=consolidate_checkmk_snapshot(H,S)
        self.assertEqual(r["hosts"]["brocade-fc01"]["overall_state"],"CRIT")
        self.assertEqual(r["hosts"]["brocade-fc01"]["host_state"],"OK")
        self.assertEqual(r["service_count"],1)
        self.assertFalse(r["runtime_authenticated"])
    def test_orphan_service_rejected(self):
        s=dict(S,services=[dict(S["services"][0],host="missing")])
        with self.assertRaises(ValueError):consolidate_checkmk_snapshot(H,s)
    def test_capture_time_mismatch_rejected(self):
        with self.assertRaises(ValueError):consolidate_checkmk_snapshot(H,dict(S,captured_at="2026-10-24T20:00:01Z"))
    def test_forged_runtime_claim_rejected(self):
        with self.assertRaises(ValueError):consolidate_checkmk_snapshot(dict(H,runtime_authenticated=True),S)
    def test_duplicate_service_rejected(self):
        with self.assertRaises(ValueError):consolidate_checkmk_snapshot(H,dict(S,services=S["services"]*2))
if __name__=="__main__":unittest.main()
