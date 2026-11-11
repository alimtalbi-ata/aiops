"""Source-level regression for the read-only ACME run navigation contract."""
import pathlib
import unittest

PORTAL = pathlib.Path(__file__).resolve().parents[1] / "app" / "portal" / "main.py"


class AcmeRunNavigationContract(unittest.TestCase):
    def test_run_link_uses_validated_id_and_url_encoding(self):
        source = PORTAL.read_text(encoding="utf-8")
        self.assertIn('if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",rid):', source)
        self.assertIn('href="/timeline?run_id=\'+quote(rid,safe="")', source)
        self.assertIn("Impact SAN → Payments (Twin, non corrélé)", source)

    def test_run_polling_discards_stale_and_cross_run_responses(self):
        source = PORTAL.read_text(encoding="utf-8")
        self.assertIn('window.addEventListener("pagehide",invalidate,{once:true});', source)
        self.assertIn('if(!active||current!==generation)return;', source)
        self.assertIn('result.run_id!==rid', source)
        self.assertIn('controller.abort()', source)
        self.assertIn('signal:controller.signal', source)

    def test_launch_still_requires_server_side_opt_in_and_token(self):
        source = PORTAL.read_text(encoding="utf-8")
        self.assertIn("if os.getenv('AIOPS_DEMO_LAUNCH_ENABLED')!='true':", source)
        self.assertIn("hmac.compare_digest(bearer,secret)", source)
        self.assertIn('if r.get("run_id")==rid and r.get("mode") in ("DEMO","REPLAY","STORY")', source)


if __name__ == "__main__":
    unittest.main()
