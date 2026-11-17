"""Source-only Portal route checks: no HTTP or browser."""
import unittest
from pathlib import Path

from scripts.acme_portal_route_inventory import (
    SCENE_CANDIDATES, SOURCE, inventory, routes_from_source,
)


class PortalRouteInventoryTests(unittest.TestCase):
    def test_real_source_routes(self):
        source = SOURCE.read_text(encoding="utf-8")
        paths = routes_from_source(source)
        for path in ("/demo-studio", "/demo-studio/run/{rid}",
                     "/timeline", "/twin", "/qualification-lab",
                     "/acme-stories", "/policy"):
            with self.subTest(path=path):
                self.assertIn(path, paths)

    def test_no_post_routes_as_capture_targets(self):
        source = SOURCE.read_text(encoding="utf-8")
        paths = routes_from_source(source)
        self.assertNotIn("/api/demo", paths)
        self.assertNotIn("/api/demo-enriched", paths)

    def test_no_invented_seven_scene_success(self):
        result = inventory(SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(len(result["scenes"]), 7)
        self.assertFalse(result["seven_scenes_browser_qualified"])
        self.assertEqual(result["live"], "NO_GO")
        worker = next(x for x in result["scenes"] if x["scene"] == "itsm_worker")
        self.assertEqual(worker["status"], "NOT_IMPLEMENTED")
        for scene in result["scenes"]:
            self.assertEqual(scene["selector"], "NOT_VERIFIED")
            self.assertEqual(scene["browser_execution"], "NOT_TESTED")

    def test_synthetic_source_not_runtime_proof(self):
        source = '@app.get("/demo-studio")\ndef demo(): pass\n'
        result = inventory(source)
        self.assertEqual(result["evidence_level"], "STATIC_SOURCE_ONLY")
        self.assertFalse(result["seven_scenes_browser_qualified"])
        self.assertEqual(result["scenes"][0]["status"], "SOURCE_ROUTE_CANDIDATE_ONLY")

    def test_route_parser_ignores_other_objects_and_post(self):
        source = ('@app.post("/danger")\ndef a(): pass\n'
                  '@other.get("/not-app")\ndef b(): pass\n'
                  '@app.get("/safe")\ndef c(): pass\n')
        self.assertEqual(routes_from_source(source), ["/safe"])


if __name__ == "__main__":
    unittest.main()
