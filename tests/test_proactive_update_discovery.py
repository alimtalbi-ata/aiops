import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"deploy"))
import proactive_update_discovery as update

class UpdateDiscoveryTests(unittest.TestCase):
    def run_case(self, protected, enabled):
        sha="a"*40
        manifest=base64.b64encode(json.dumps({"schema":1,"enabled":enabled}).encode()).decode()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(update.Path,"home",return_value=Path(tmp)), patch.object(update,"get",side_effect=[{"protected":protected,"commit":{"sha":sha}},{"content":manifest}]):
                update.main()
            return json.loads((Path(tmp)/".local/state/aiops2-proactive/update-candidate.json").read_text())
    def test_unprotected(self):
        self.assertEqual(self.run_case(False,True)["state"],"UPDATE_BLOCKED")
    def test_disabled(self):
        self.assertEqual(self.run_case(True,False)["state"],"UPDATE_BLOCKED")
    def test_enabled_never_activates(self):
        result=self.run_case(True,True)
        self.assertEqual(result["state"],"REVIEW_REQUIRED")
        self.assertIs(result["activation_authorized"],False)
