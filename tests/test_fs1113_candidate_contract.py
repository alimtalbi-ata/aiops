"""FS1113 static safety contract; not a substitute for authenticated Chromium E2E."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts/fs/fs1097_patch.py"
GATE = ROOT / "scripts/fs/FS.1113-history-race-candidate-validation.sh"


class FS1113CandidateContract(unittest.TestCase):
    def test_stale_history_responses_cannot_render(self):
        source = PATCH.read_text(encoding="utf-8")
        self.assertIn("new AbortController()", source)
        self.assertIn("historyAbortController.abort()", source)
        self.assertIn("signal:controller.signal", source)
        self.assertIn("const requestId=++historyRequestId", source)
        self.assertGreaterEqual(source.count("if(requestId!==historyRequestId)return;"), 2)
        self.assertIn("if(requestId!==historyRequestId||error.name===\"AbortError\")return", source)
        self.assertIn("if(requestId===historyRequestId){button.disabled=false", source)
        self.assertIn("legend.replaceChildren()", source)
        self.assertIn("data.metric!==metric||data.window!==windowSize", source)

    def test_candidate_rebuilt_before_browser_gate_and_prod_checked(self):
        source = GATE.read_text(encoding="utf-8")
        build = 'FS.1097-build-history-chart-candidate.sh'
        browser = 'FS.1107-full-history-candidate-external-first-browser.sh'
        self.assertIn("set -euo pipefail", source)
        self.assertIn("EXPECTED_PROD=aiops2-portal:fs1073-csp-candidate", source)
        self.assertIn('[[ "$PROD_BEFORE" == "$EXPECTED_PROD" ]]', source)
        self.assertLess(source.index(build), source.index(browser))
        self.assertIn('[[ "$prod_after" != "$PROD_BEFORE" ]]', source)
        self.assertIn("trap check_production_on_exit EXIT", source)

    def test_production_identity_is_guarded_not_only_tag(self):
        source = GATE.read_text(encoding="utf-8")
        self.assertIn("PROD_ID_BEFORE=", source)
        self.assertIn("PROD_IMAGE_ID_BEFORE=", source)
        self.assertIn('prod_id_after="$(docker inspect', source)
        self.assertIn('prod_image_id_after="$(docker inspect', source)
        self.assertIn('"$prod_id_after" != "$PROD_ID_BEFORE"', source)
        self.assertIn('"$prod_image_id_after" != "$PROD_IMAGE_ID_BEFORE"', source)
        self.assertIn("FS1113_ERROR=PRODUCTION_CONTAINER_OR_IMAGE_ID_CHANGED", source)


if __name__ == "__main__":
    unittest.main()
