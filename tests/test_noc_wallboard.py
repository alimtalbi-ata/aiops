import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
from demo.noc_synthetic_snapshot import build_noc_snapshot
from demo.noc_wallboard import render_noc_wallboard, main

class NocWallboardTests(unittest.TestCase):
    def snapshot(self):
        source=Path(__file__).resolve().parents[1]/"demo/rag_ops_fixture_catalog.json"
        return build_noc_snapshot(json.loads(source.read_text(encoding="utf8")))
    def test_realistic_synthetic_wallboard(self):
        page=render_noc_wallboard(self.snapshot())
        self.assertIn("NOC Command Center",page)
        self.assertIn("ACME Payments",page)
        self.assertIn("brocade-fc01",page)
        self.assertIn("DONNÉES SYNTHÉTIQUES",page)
        self.assertIn('data-filter="CRIT"',page)
        self.assertNotIn("checkmk_live=true",page)
    def test_xss_is_escaped(self):
        state=self.snapshot()
        state["hosts"]["<img src=x onerror=alert(1)>"]={"state":"CRIT","alerts":1}
        page=render_noc_wallboard(state)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;",page)
        self.assertNotIn("<img src=x onerror=alert(1)>",page)
    def test_forged_live_attestation_fails(self):
        state=self.snapshot()
        state["checkmk_live"]=True
        with self.assertRaises(ValueError):
            render_noc_wallboard(state)
    def test_invalid_state_fails(self):
        state=self.snapshot()
        state["hosts"]["brocade-fc01"]["state"]="PWN"
        with self.assertRaises(ValueError):
            render_noc_wallboard(state)
    def test_cli_outputs_html_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/"noc.html"
            with patch.object(sys,"argv",["noc","--output",str(out)]): main()
            self.assertIn("ACME Payments",out.read_text(encoding="utf8"))
            with patch.object(sys,"argv",["noc","--output",str(out)]), self.assertRaises(FileExistsError):main()
if __name__=="__main__":unittest.main()
