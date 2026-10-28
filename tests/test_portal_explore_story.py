"""Offline HTTP/security regressions for Explore/Story. No runtime integration claim."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-only-internal-test"}):
    from portal import main
from fastapi.testclient import TestClient
from portal.acme_impact_read_model import build_acme_impact_read_model

TOKEN = "synthetic-explore-story-viewer"
PATH = "/api/demo/explore-story/control"


class ExploreStoryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def request(self, action="start", cursor=0, mode="explore", token=TOKEN):
        return self.client.post(PATH, json={"action": action, "cursor": cursor, "mode": mode},
                                headers={"Authorization": "Bearer " + token})

    def test_portal_navigation_and_anonymous_shell_no_fixture_read(self):
        with patch("portal.acme_explore_story._load_or_503",
                   side_effect=AssertionError("no fixture on anonymous page")):
            page = self.client.get("/demo/explore-story")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Explore / Story", page.text)
        self.assertIn("UNKNOWN", page.text)
        self.assertNotIn("SIM-ACME-", page.text)
        self.assertEqual(page.headers["cache-control"], "no-store")
        self.assertEqual(page.headers["x-frame-options"], "DENY")
        self.assertIn("script-src 'self'", page.headers["content-security-policy"])
        home = self.client.get("/")
        self.assertIn('href="/demo/explore-story"', home.text)
        js = self.client.get("/assets/acme-explore-story.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn('credentials: "omit"', js.text)
        self.assertNotIn("localStorage", js.text)

    def test_auth_denial_precedes_fixture_read(self):
        for headers in ({}, {"Authorization": "Basic " + TOKEN},
                        {"Authorization": "Bearer wrong"},
                        {"Authorization": "Bearer " + TOKEN + " extra"}):
            with self.subTest(headers=headers), patch(
                "portal.acme_explore_story._load_or_503",
                side_effect=AssertionError("fixture must not be read")
            ) as load:
                r = self.client.post(PATH, json={"action": "start", "cursor": 0,
                                                  "mode": "story"}, headers=headers)
                self.assertEqual(r.status_code, 401)
                self.assertEqual(r.json()["detail"], "invalid_portal_read_token")
                self.assertEqual(r.headers["cache-control"], "no-store")
                load.assert_not_called()
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch(
            "portal.acme_explore_story._load_or_503",
            side_effect=AssertionError("fixture must not be read")
        ):
            self.assertEqual(self.request().status_code, 503)

    def test_explore_story_share_exact_synthetic_fixture_and_never_attest_live(self):
        fixture = build_acme_impact_read_model()
        explore = self.request(mode="explore")
        story = self.request(mode="story")
        self.assertEqual(explore.status_code, 200)
        self.assertEqual(story.status_code, 200)
        a, b = explore.json(), story.json()
        self.assertEqual(a["scenario"], b["scenario"])
        self.assertEqual(a["timeline"], b["timeline"])
        self.assertEqual(a["source_sha256"], b["source_sha256"])
        self.assertEqual(a["source_sha256"], fixture["source_sha256"])
        self.assertEqual(a["scenario"]["impact_path"], fixture["impact_path"])
        self.assertEqual(len(a["timeline"]), len(fixture["checkpoint_evidence"]))
        self.assertEqual(a["provenance"], "SIMULATED_TARGET")
        self.assertFalse(a["playing"])
        self.assertTrue(b["playing"])
        for item in (a, b):
            self.assertFalse(item["runtime_attested"])
            self.assertFalse(item["production_qualified"])
            self.assertFalse(item["live_remediation_authorized"])
            self.assertIsNone(item["scenario"]["ticket_id"])
            self.assertIsNone(item["scenario"]["event_timestamp_utc"])
            self.assertNotIn(TOKEN, str(item))
            self.assertTrue(all(s["status"] == "MISSING" for s in item["timeline"]))
            self.assertEqual(explore.headers["cache-control"], "no-store")

    def test_story_controls_deterministic_and_no_backend_writes(self):
        with patch.object(main, "post_json", side_effect=AssertionError("no backend write")), patch.object(
            main, "get_json", side_effect=AssertionError("no backend read")
        ):
            first = self.request(mode="story").json()
            advanced = self.request("advance", 0, "story").json()
            paused = self.request("pause", 1, "story").json()
            reset = self.request("reset", 6, "story").json()
            replay = self.request("replay", 6, "story").json()
            last = self.request("advance", len(first["timeline"]) - 1, "story").json()
        self.assertEqual((first["cursor"], advanced["cursor"], paused["cursor"],
                          reset["cursor"], replay["cursor"], last["cursor"]),
                         (0, 1, 1, 0, 0, len(first["timeline"]) - 1))
        self.assertTrue(replay["playing"])
        self.assertFalse(paused["playing"])
        self.assertFalse(reset["playing"])
        self.assertFalse(last["playing"])
        self.assertEqual(self.request("replay", 3, "story").json(), replay)

    def test_rejects_malformed_actions_and_cursors_before_fixture_read(self):
        bad = [
            {"action": "execute", "cursor": 0, "mode": "story"},
            {"action": "start", "cursor": -1, "mode": "story"},
            {"action": "start", "cursor": True, "mode": "story"},
            {"action": "start", "cursor": "0", "mode": "story"},
            {"action": ["start"], "cursor": 0, "mode": "story"},
            {"action": "start", "cursor": 0, "mode": ["story"]},
            {"action": "start", "cursor": 0, "mode": "LIVE"},
            {"action": "start", "cursor": 0, "mode": "story", "tenant_id": "other"},
            {"action": "start", "cursor": 0},
        ]
        with patch("portal.acme_explore_story._load_or_503",
                   side_effect=AssertionError("no fixture on invalid input")) as load:
            for payload in bad:
                with self.subTest(payload=payload):
                    r = self.client.post(PATH, json=payload,
                                         headers={"Authorization": "Bearer " + TOKEN})
                    self.assertEqual(r.status_code, 422)
                    self.assertEqual(r.headers["cache-control"], "no-store")
            load.assert_not_called()
        self.assertEqual(self.request("advance", 999, "story").status_code, 422)

    def test_invalid_fixture_is_unknown_not_success(self):
        with patch("portal.acme_explore_story._load_or_503",
                   side_effect=main.HTTPException(status_code=503, detail="secret")):
            r = self.request(mode="story")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["state"], "UNKNOWN")
        self.assertNotIn("secret", r.text)
        self.assertEqual(r.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
