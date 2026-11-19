import base64
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"deploy"))
import proactive_update_discovery as update

class UpdateDiscoveryTests(unittest.TestCase):
    def manifest(self, **overrides):
        value={"schema":1,"enabled":True,"expires_at":(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=1)).isoformat(),"source_sha":"a"*40,"artifact_digest":"sha256:"+"b"*64}
        value.update(overrides)
        return base64.b64encode(json.dumps(value).encode()).decode()

    def run_case(self, protected=True, manifest=None):
        sha="a"*40
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(update.Path,"home",return_value=Path(tmp)),patch.object(update,"get",side_effect=[{"protected":protected,"commit":{"sha":sha}},{"content":manifest or self.manifest()}]):
                update.main()
            return json.loads((Path(tmp)/".local/state/aiops2-proactive/update-candidate.json").read_text())

    def test_unprotected(self):
        self.assertEqual(self.run_case(False)["state"],"UPDATE_BLOCKED")

    def test_disabled(self):
        self.assertEqual(self.run_case(manifest=self.manifest(enabled=False))["state"],"UPDATE_BLOCKED")

    def test_valid_manifest_never_activates(self):
        result=self.run_case()
        self.assertEqual(result["state"],"REVIEW_REQUIRED")
        self.assertIs(result["activation_authorized"],False)

    def test_expired_manifest(self):
        expired=self.manifest(expires_at=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=1)).isoformat())
        self.assertEqual(self.run_case(manifest=expired)["state"],"UPDATE_BLOCKED")

    def test_bad_digest(self):
        self.assertEqual(self.run_case(manifest=self.manifest(artifact_digest="sha256:bad"))["state"],"UPDATE_BLOCKED")

    def test_api_failure_is_fail_closed(self):\n        with tempfile.TemporaryDirectory() as tmp:\n            with patch.object(update.Path,"home",return_value=Path(tmp)),patch.object(update,"get",side_effect=OSError("API unavailable")):\n                update.main()\n            result=json.loads((Path(tmp)/".local/state/aiops2-proactive/update-candidate.json").read_text())\n            self.assertEqual(result["state"],"UPDATE_BLOCKED")\n            self.assertIs(result["activation_authorized"],False)\n\n    def test_non_object_manifest(self):
        raw=base64.b64encode(json.dumps(["not","object"]).encode()).decode()
        self.assertEqual(self.run_case(manifest=raw)["state"],"UPDATE_BLOCKED")
