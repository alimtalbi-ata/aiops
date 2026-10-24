"""Run all nine STAR checkpoints in actual Chromium against synthetic fixtures."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from demo.star_offline_chromium_fixture import render_isolated_fixtures
from demo.star_snapshot_choreography import CUES
from demo.star_png_integrity import inspect_png

class NineSceneChromiumQualification(unittest.TestCase):
    def test_nine_synthetic_scenes_render_and_sha_match(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fixture=root/"fixtures"
            fixture.mkdir()
            mapping={}
            tasks=[]
            for cue in CUES:
                name=cue.cue+".html"
                (fixture/name).write_text(
                    '<!doctype html><html><body><h1>TEST FIXTURE ONLY</h1><p>'
                    +cue.cue+' / '+cue.service+' / '+cue.required_state
                    +'</p></body></html>', encoding="utf-8")
                mapping[cue.cue]=name
                tasks.append({"cue":cue.cue,"capture_performed":False,
                              "authenticated_runtime_proof":False})
            plan={"schema":"star-browser-capture-tasks-v1","run_id":"RUN-TEST-NINE",
                  "browser_executed":False,"runtime_proof_count":0,
                  "live_action_authorized":False,"tasks":tasks}
            result=asyncio.run(render_isolated_fixtures(plan,mapping,fixture,root/"out"))
            self.assertEqual(len(result["captures"]),9)
            self.assertEqual(result["runtime_proof_count"],0)
            self.assertFalse(result["live_action_authorized"])
            self.assertEqual([x["cue"] for x in result["captures"]],[c.cue for c in CUES])
            for capture in result["captures"]:
                digest, size=inspect_png(root/"out"/capture["file"])
                self.assertEqual(digest,capture["sha256"])
                self.assertGreater(size,100)
                self.assertEqual(capture["origin"],"SYNTHETIC_LOCAL_FIXTURE")
                self.assertFalse(capture["runtime_authenticated"])
                self.assertFalse(capture["business_state_verified"])

if __name__=="__main__":
    unittest.main()
