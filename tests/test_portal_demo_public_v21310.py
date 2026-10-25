"""Offline regression tests for the public synthetic-only router."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import unittest
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, FileResponse

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
MODULE = APP_ROOT / "portal" / "portal_demo_public_v21310.py"
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

    def test_public_router_is_mounted_on_existing_portal_app(self):
        # Import in a child process so the synthetic internal token cannot leak
        # into other tests and no runtime service or listener is contacted.
        env = os.environ.copy()
        env.pop("AIOPS_ADMIN_TOKEN", None)
        env["AIOPS_INTERNAL_TOKEN"] = "synthetic-ci-only-token"
        code = (
            "import json; from portal.main import app; "
            "print(json.dumps([{'path':r.path,'methods':sorted(r.methods or [])} "
            "for r in app.routes if r.path in {'/demo/','/demo/star'}]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=APP_ROOT, env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        routes = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual({item["path"] for item in routes}, {"/demo/", "/demo/star"})
        for item in routes:
            self.assertIn("GET", item["methods"])
            self.assertTrue(set(item["methods"]).issubset({"GET", "HEAD"}))


if __name__ == "__main__":
    unittest.main()
