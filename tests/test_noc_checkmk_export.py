import unittest
from demo.noc_checkmk_export import parse_host_status_export
BASE={"schema":"aiops-checkmk-host-export-v1","source":"CHECKMK_EXPORT",
      "read_only":True,"live_remediation_authorized":False,
      "captured_at":"2026-10-24T20:00:00Z",
      "hosts":[{"name":"brocade-fc01","state":2,"output":"Synthetic test export"}]}
class CheckmkExportTests(unittest.TestCase):
    def parse(self,p):return parse_host_status_export(p,now_utc="2026-10-24T20:01:00Z")
    def test_valid_export_remains_unverified(self):
        r=self.parse(BASE)
        self.assertEqual(r["hosts"]["brocade-fc01"]["state"],"CRIT")
        self.assertFalse(r["runtime_authenticated"])
        self.assertEqual(r["age_seconds"],60)
    def test_expired_export_rejected(self):
        with self.assertRaises(ValueError):parse_host_status_export(BASE,now_utc="2026-10-24T20:20:00Z")
    def test_duplicate_assets_rejected(self):
        p=dict(BASE);p["hosts"]=BASE["hosts"]*2
        with self.assertRaises(ValueError):self.parse(p)
    def test_future_export_rejected(self):
        with self.assertRaises(ValueError):parse_host_status_export(BASE,now_utc="2026-10-24T19:59:00Z")
    def test_unsafe_claim_rejected(self):
        p=dict(BASE);p["live_remediation_authorized"]=True
        with self.assertRaises(ValueError):self.parse(p)
if __name__=="__main__":unittest.main()
