import unittest
from demo.noc_livestatus_import import normalize_livestatus_hosts
NOW="2026-10-24T20:01:00Z"
TIME="2026-10-24T20:00:00Z"
class LivestatusImportTests(unittest.TestCase):
    def test_mapping(self):
        obj=normalize_livestatus_hosts([{"name":"brocade-fc01","state":2,"plugin_output":"Port down"}],captured_at=TIME,now_utc=NOW)
        self.assertEqual(obj["hosts"]["brocade-fc01"]["state"],"CRIT")
        self.assertEqual(obj["transport"],"OFFLINE_LIVESTATUS_EXPORT")
        self.assertFalse(obj["runtime_authenticated"])
    def test_forbid_extra_unreviewed_columns(self):
        with self.assertRaises(ValueError):
            normalize_livestatus_hosts([{"name":"x","state":0,"plugin_output":"ok","command":"delete"}],captured_at=TIME,now_utc=NOW)
    def test_reject_invalid_state(self):
        with self.assertRaises(ValueError):
            normalize_livestatus_hosts([{"name":"x","state":True,"plugin_output":"ok"}],captured_at=TIME,now_utc=NOW)
    def test_stale_export_rejected(self):
        with self.assertRaises(ValueError):
            normalize_livestatus_hosts([{"name":"x","state":0,"plugin_output":"ok"}],captured_at=TIME,now_utc="2026-10-24T21:00:00Z")
if __name__=="__main__":unittest.main()
