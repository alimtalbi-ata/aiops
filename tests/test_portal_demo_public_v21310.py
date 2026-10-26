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
from unittest.mock import patch, MagicMock

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
        self.assertIn("Générer la vidéo complète", html)
        self.assertIn("PAYMENTS_P2", html)
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
        self.assertEqual(routes,{"/demo/","/demo/star","/demo/video","/demo/video/{job_id}","/demo/video/{job_id}/artifact/{artifact}"})


    def test_video_generation_is_disabled_by_default(self):
        old = os.environ.pop("AIOPS_DEMO_VIDEO_ENABLED", None)
        try:
            with self.assertRaises(HTTPException) as ctx:
                mod.start_video({"scenario":"SAN_FABRIC_P1"})
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("video_generation_disabled", ctx.exception.detail)
        finally:
            if old is not None:
                os.environ["AIOPS_DEMO_VIDEO_ENABLED"] = old

    def test_video_scenario_allowlist_rejects_untrusted_values(self):
        with self.assertRaises(HTTPException) as ctx:
            mod.start_video({"scenario":"../../etc/passwd"})
        self.assertEqual(ctx.exception.status_code, 422)
        with self.assertRaises(HTTPException) as ctx:
            mod.start_video({"scenario":[]})
        self.assertEqual(ctx.exception.status_code, 422)
        with self.assertRaises(HTTPException) as ctx:
            mod.video_status("../" + "a" * 30)
        self.assertEqual(ctx.exception.status_code, 404)
        with self.assertRaises(HTTPException) as ctx:
            mod.video_artifact("a" * 32, "../../etc/passwd")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_enabled_video_job_uses_fixed_command_and_unique_output(self):
        import tempfile
        from pathlib import Path
        old_enabled = os.environ.get("AIOPS_DEMO_VIDEO_ENABLED")
        old_root, old_runs = mod.REPO_ROOT, mod.RUNS_ROOT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            (root / "demo").mkdir(parents=True)
            (root / "demo" / "generate_demo_video.py").write_text("# fixture", encoding="utf-8")
            mod.REPO_ROOT = root
            mod.RUNS_ROOT = root / "dist" / "demo-video-runs"
            proc = MagicMock()
            proc.poll.return_value = None
            try:
                os.environ["AIOPS_DEMO_VIDEO_ENABLED"] = "true"
                with patch.object(mod.subprocess, "Popen", return_value=proc) as popen:
                    response = mod.start_video({"scenario":"PAYMENTS_P2"})
                self.assertEqual(response.status_code, 202)
                self.assertEqual(__import__("json").loads(response.body)["status"], "running")
                args, kwargs = popen.call_args
                self.assertEqual(args[0][:3], [mod.sys.executable, "-m", "demo.generate_demo_video"])
                self.assertEqual(args[0][3:5], ["--scenario", "PAYMENTS_P2"])
                self.assertEqual(kwargs["cwd"], str(root))
                self.assertEqual(kwargs["stdin"], mod.subprocess.DEVNULL)
                self.assertTrue(kwargs["start_new_session"])
                output = Path(args[0][-1])
                self.assertEqual(output.parent, mod.RUNS_ROOT)
                self.assertEqual(len(output.name), 32)
            finally:
                if old_enabled is None:
                    os.environ.pop("AIOPS_DEMO_VIDEO_ENABLED", None)
                else:
                    os.environ["AIOPS_DEMO_VIDEO_ENABLED"] = old_enabled
                mod.REPO_ROOT, mod.RUNS_ROOT = old_root, old_runs
                with mod._jobs_lock:
                    mod._jobs.clear()
                    mod._recent_starts.clear()

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
