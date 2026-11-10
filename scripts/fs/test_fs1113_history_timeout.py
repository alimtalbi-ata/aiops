#!/usr/bin/env python3
"""Regression guard: active history timeout must show failure, stale abort stays silent."""
import pathlib
import re
import unittest

SOURCE = pathlib.Path(__file__).with_name("fs1097_patch.py")

class HistoryTimeoutContract(unittest.TestCase):
    def test_timeout_is_bounded_and_cleared(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertRegex(source, r"historyTimeout=setTimeout\(\(\)=>\{historyTimedOut=true;controller\.abort\(\},20000\)")
        self.assertIn("finally{clearTimeout(historyTimeout);", source)

    def test_timeout_failure_not_swallowed_as_stale_abort(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('if(requestId!==historyRequestId||(!historyTimedOut&&(controller.signal.aborted||error?.name==="AbortError")))return;', source)
        self.assertIn('status.textContent="Historique indisponible · réessayez ou contactez l’exploitation"', source)

    def test_request_generation_still_guards_old_responses(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("const requestId=++historyRequestId;", source)
        self.assertIn("if(requestId!==historyRequestId)return;", source)

if __name__ == "__main__":
    unittest.main()
