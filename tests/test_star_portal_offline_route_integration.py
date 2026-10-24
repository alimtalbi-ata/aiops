"""ASGI-only integration: existing portal, synthetic replay artifacts, no network I/O."""
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal.star_legacy_readonly import CUES, router

RUN = "RUN-STAR-SYNTHETIC-249"

def fixture(scenario="SAN_FABRIC_P1"):
    return {
        "schema": "star-legacy-portal-binding/v1", "run_id": RUN,
        "scenario": scenario, "replay_status": "BLOCKED",
        "replay_input_content_sha256": {k: "0"*64 for k in ("run", "ledger", "evidence")},
        "chronology_proven_from_declared_timestamps": False,
        "storyboard": {
            "schema": "star-portal-transport-v1", "run_id": RUN, "scenario": scenario,
            "frames": [{"step": cue, "application": app, "expected_view": view,
                        "expected_state": state, "capture_status": "missing",
                        "runtime_verified": False, "action_allowed": False}
                       for cue, app, view, state in CUES],
            "safety": {"read_only": True, "runtime_authenticated": False,
                       "portal_integration_qualified": False, "remediation_authorized": False}},
        "bindings": [{"cue": cue, "binding_status": "unbound", "replay_reference": None}
                     for cue, *_ in CUES],
        "safety": {"read_only": True, "synthetic_only": True,
                   "runtime_authenticated": False, "business_validated": False,
                   "human_approval_authenticated": False, "live_remediation_authorized": False,
                   "portal_integration_qualified": False}}

class ExistingPortalReplayRouteTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict(os.environ, {
            "AIOPS_STAR_REPLAY_VIEW_ENABLED": "true",
            "AIOPS_STAR_OFFLINE_DIR": str(self.root),
            "AIOPS_STAR_VIEW_USER": "operator",
            "AIOPS_STAR_VIEW_PASSWORD": "synthetic-test-password"})
        env.start()
        self.addCleanup(env.stop)
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.auth = {"Authorization": "Basic " + base64.b64encode(
            b"operator:synthetic-test-password").decode("ascii")}

    def stage(self, doc=None, raw=None):
        if raw is None:
            raw = json.dumps(fixture() if doc is None else doc,
                             sort_keys=True, separators=(",", ":")).encode()
        (self.root / (RUN + ".json")).write_bytes(raw)
        (self.root / (RUN + ".sha256")).write_text(hashlib.sha256(raw).hexdigest()+"\n")

    def get(self):
        return self.client.get("/demo/star-replay/"+RUN, headers=self.auth)

    def test_router_is_registered_exactly_once_in_existing_portal(self):
        from portal.main import app
        self.assertEqual([r.path for r in app.routes].count("/demo/star-replay/{run_id}"), 1)

    def test_both_scenarios_render_nine_unattested_checkpoints(self):
        for scenario in ("SAN_FABRIC_P1", "PAYMENTS_P2"):
            with self.subTest(scenario=scenario):
                self.stage(fixture(scenario))
                r = self.get()
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.text.count('<section id="scene-'), 9)
                self.assertIn(scenario, r.text)
                self.assertIn("SYNTHÉTIQUE", r.text)
                self.assertIn("origine non authentifiée", r.text)
                self.assertNotIn("<script", r.text)
                self.assertEqual(r.headers["cache-control"], "no-store, max-age=0")
                self.assertEqual(r.headers["x-content-type-options"], "nosniff")
                self.assertEqual(r.headers["referrer-policy"], "no-referrer")
                self.assertEqual(self.client.post("/demo/star-replay/"+RUN).status_code, 405)

    def test_feature_flag_default_off(self):
        self.stage()
        with patch.dict(os.environ, {"AIOPS_STAR_REPLAY_VIEW_ENABLED": "false"}):
            self.assertEqual(self.get().status_code, 404)

    def test_authentication_missing_invalid_or_unconfigured(self):
        self.stage()
        self.assertEqual(self.client.get("/demo/star-replay/"+RUN).status_code, 401)
        self.assertEqual(self.client.get("/demo/star-replay/"+RUN,
                         auth=("operator", "wrong")).status_code, 401)
        with patch.dict(os.environ, {"AIOPS_STAR_VIEW_PASSWORD": ""}):
            self.assertEqual(self.get().status_code, 503)

    def test_remote_plaintext_denied_even_with_valid_credentials(self):
        self.stage()
        remote = TestClient(self.client.app, client=("198.51.100.42", 44321))
        self.assertEqual(remote.get("/demo/star-replay/"+RUN,
                                    headers=self.auth).status_code, 403)

    def test_missing_corrupt_or_symlink_artifact_fail_closed(self):
        self.assertEqual(self.get().status_code, 503)
        self.stage()
        (self.root / (RUN+".json")).write_bytes(b"tampered")
        self.assertEqual(self.get().status_code, 503)
        self.stage()
        p = self.root / (RUN+".json")
        target = self.root / "other.json"
        p.rename(target)
        p.symlink_to(target)
        self.assertEqual(self.get().status_code, 503)

    def test_duplicate_json_keys_rejected(self):
        self.stage(raw=b'{"schema":"star-legacy-portal-binding/v1","schema":"other"}')
        self.assertEqual(self.get().status_code, 503)

    def test_forbidden_authority_claims_rejected(self):
        for key in ("human_approval_authenticated", "runtime_authenticated",
                    "business_validated", "live_remediation_authorized"):
            with self.subTest(key=key):
                doc = fixture()
                doc["safety"][key] = True
                self.stage(doc)
                self.assertEqual(self.get().status_code, 503)

    def test_private_data_and_wrong_application_rejected(self):
        doc = fixture()
        doc["storyboard"]["frames"][0]["token"] = "PRIVATE_DO_NOT_RENDER"
        self.stage(doc)
        r = self.get()
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("PRIVATE_DO_NOT_RENDER", r.text)
        doc = fixture()
        doc["storyboard"]["frames"][4]["application"] = "grafana"
        self.stage(doc)
        self.assertEqual(self.get().status_code, 503)

    def test_contradictory_run_and_reverse_chronology_rejected(self):
        doc = fixture()
        doc["storyboard"]["run_id"] = "RUN-OTHER"
        self.stage(doc)
        self.assertEqual(self.get().status_code, 503)
        doc = fixture()
        for i, (source, stamp) in enumerate((
            ("events", "2026-10-24T01:00:02Z"), ("stages", "2026-10-24T01:00:01Z"))):
            doc["bindings"][i] = {
                "cue": CUES[i][0], "binding_status": "operator_declared_unattested",
                "replay_reference": {"source": source, "source_index": 1,
                                     "declared_timestamp": stamp}}
        self.stage(doc)
        self.assertEqual(self.get().status_code, 503)

if __name__ == "__main__":
    unittest.main()
