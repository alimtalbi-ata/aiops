import unittest
from demo.noc_platform_registry import COMPONENTS,build_portal_component_registry

class PlatformRegistryTests(unittest.TestCase):
    def test_all_components_unknown_by_default(self):
        obj=build_portal_component_registry()
        self.assertGreaterEqual(len(obj["items"]),19)
        self.assertTrue(all(x["state"]=="UNKNOWN" and not x["available_in_portal"] for x in obj["items"]))
        self.assertEqual(len({x["path"] for x in obj["items"]}),len(COMPONENTS))
        self.assertEqual(obj["entrypoint"],"http://10.79.94.202:17777/")
        self.assertIs(obj["live_remediation_authorized"],False)

    def test_authenticated_fresh_observation(self):
        o={"thruk":{"state":"OK","observed_at":"2026-10-25T12:00:00Z","authenticated":True}}
        obj=build_portal_component_registry(o,now_utc="2026-10-25T12:01:00Z")
        self.assertEqual(next(x for x in obj["items"] if x["id"]=="thruk")["state"],"OK")
        self.assertFalse(next(x for x in obj["items"] if x["id"]=="thruk")["available_in_portal"])

    def test_stale_or_unverified_unknown(self):
        o={"checkmk":{"state":"OK","observed_at":"2026-10-25T11:00:00Z","authenticated":True},
           "n8n":{"state":"OK","observed_at":"2026-10-25T12:00:00Z","authenticated":False}}
        obj=build_portal_component_registry(o,now_utc="2026-10-25T12:01:00Z")
        self.assertEqual([x["state"] for x in obj["items"] if x["id"] in ("checkmk","n8n")],["UNKNOWN","UNKNOWN"])

    def test_future_observation_stays_unknown(self):
        o={"thruk":{"state":"OK","observed_at":"2026-10-25T12:02:00Z","authenticated":True}}
        obj=build_portal_component_registry(o,now_utc="2026-10-25T12:01:00Z")
        self.assertEqual(next(x for x in obj["items"] if x["id"]=="thruk")["state"],"UNKNOWN")

    def test_unknown_component_rejected(self):
        with self.assertRaisesRegex(ValueError,"unexpected component identity"):
            build_portal_component_registry({"fake":{}})

    def test_invalid_payload_rejected(self):
        with self.assertRaisesRegex(ValueError,"invalid component observation"):
            build_portal_component_registry({"thruk":{"state":"OK","authenticated":True}})

    def test_unhashable_state_rejected_cleanly(self):
        with self.assertRaisesRegex(ValueError,"invalid component observation"):
            build_portal_component_registry({"thruk":{"state":[],"observed_at":"2026-10-25T12:00:00Z","authenticated":True}})

    def test_bool_and_out_of_range_freshness_policy_rejected(self):
        for value in (True,False,0,3601,300.0,"300"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,"invalid observations"):
                build_portal_component_registry(max_age_seconds=value)

    def test_invalid_clock_rejected(self):
        for value in ("2026-10-25T12:00:00+00:00","not-a-time","2026-02-30T12:00:00Z"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,"invalid clock"):
                build_portal_component_registry(now_utc=value)

    def test_invalid_authenticated_observation_timestamp_rejected(self):
        for value in ("bad-time","2026-10-25T12:00:00+00:00","2026-02-30T12:00:00Z"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,"invalid observation timestamp"):
                build_portal_component_registry(
                    {"thruk":{"state":"OK","observed_at":value,"authenticated":True}},
                    now_utc="2026-10-25T12:01:00Z")

if __name__=="__main__":
    unittest.main()
