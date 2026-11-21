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

    def run_case(self, protected=True, manifest=None, final=None):
        sha="a"*40
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(update.Path,"home",return_value=Path(tmp)),patch.object(update,"get",side_effect=[{"protected":protected,"commit":{"sha":sha}},{"content":manifest or self.manifest()},final if final is not None else {"protected":True,"commit":{"sha":sha}}]):
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

    def test_api_failure_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(update.Path,"home",return_value=Path(tmp)),patch.object(update,"get",side_effect=OSError("API unavailable")):
                update.main()
            result=json.loads((Path(tmp)/".local/state/aiops2-proactive/update-candidate.json").read_text())
            self.assertEqual(result["state"],"UPDATE_BLOCKED")
            self.assertIs(result["activation_authorized"],False)

    def test_non_object_manifest(self):
        raw=base64.b64encode(json.dumps(["not","object"]).encode()).decode()
        self.assertEqual(self.run_case(manifest=raw)["state"],"UPDATE_BLOCKED")

    def test_changed_reference_blocks(self):
        self.assertEqual(self.run_case(final={"protected":True,"commit":{"sha":"c"*40}})["state"],"UPDATE_BLOCKED")

    def test_lost_protection_blocks(self):
        self.assertEqual(self.run_case(final={"protected":False,"commit":{"sha":"a"*40}})["state"],"UPDATE_BLOCKED")

    def test_final_api_failure_blocks(self):
        self.assertEqual(self.run_case(final=OSError("API unavailable"))["state"],"UPDATE_BLOCKED")

    def test_contended_lock_does_not_read_or_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/".local/state/aiops2-proactive"
            root.mkdir(parents=True)
            target=root/"update-candidate.json"
            target.write_text("{}")
            with (root/"update-discovery.lock").open("a") as lock:
                update.fcntl.flock(lock,update.fcntl.LOCK_EX)
                with patch.object(update.Path,"home",return_value=Path(tmp)),patch.object(update,"get") as get:
                    update.main()
                    get.assert_not_called()
                self.assertEqual(target.read_text(),"{}")
