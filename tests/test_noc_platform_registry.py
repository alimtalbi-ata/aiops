import unittest
from demo.noc_platform_registry import COMPONENTS,build_portal_component_registry
class PlatformRegistryTests(unittest.TestCase):
    def test_all_components_unknown_by_default(self):
        obj=build_portal_component_registry()
        self.assertGreaterEqual(len(obj["items"]),19)
        self.assertTrue(all(x["state"]=="UNKNOWN" and not x["available_in_portal"] for x in obj["items"]))
        self.assertEqual(len({x["path"] for x in obj["items"]}),len(COMPONENTS))
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
    def test_unknown_component_rejected(self):
        with self.assertRaises(ValueError):build_portal_component_registry({"fake":{}})
    def test_invalid_payload_rejected(self):
        with self.assertRaises(ValueError):build_portal_component_registry({"thruk":{"state":"OK","authenticated":True}})
if __name__=="__main__":unittest.main()
