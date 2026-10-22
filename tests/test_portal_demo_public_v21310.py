"""Offline regression tests for the public synthetic-only router."""
import importlib.util
import pathlib
import unittest
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, FileResponse

MODULE = pathlib.Path(__file__).resolve().parents[2] / "app/portal/portal_demo_public_v21310.py"
spec = importlib.util.spec_from_file_location("demo_public", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class DemoPublicTests(unittest.TestCase):
    def test_catalog_contains_no_historical_links(self):
        result = mod.catalog()
        self.assertIsInstance(result, HTMLResponse)
        html = result.body.decode()
        self.assertIn("/demo/star", html)
        self.assertNotIn("/demo/view/AIOPS-REAL-STACK-REPLAY.html", html)
    def test_asset_missing_fails_closed(self):
        old = mod.ASSET
        mod.ASSET = pathlib.Path("/nonexistent/aiops-demo-star.html")
        try:
            with self.assertRaises(HTTPException) as ctx:
                mod.star()
            self.assertEqual(ctx.exception.status_code,503)
        finally:
            mod.ASSET=old
    def test_expected_router_paths(self):
        routes = {r.path for r in mod.router.routes}
        self.assertEqual(routes,{"/demo/","/demo/star"})

if __name__ == "__main__":
    unittest.main()
