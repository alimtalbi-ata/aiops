"""Offline regression tests for the public synthetic-only router."""
import importlib.util
import json
import hashlib
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
        tracked_env = (
            "AIOPS_DEMO_VIDEO_ENABLED", "AIOPS_INTERNAL_TOKEN",
            "AIOPS_ADMIN_TOKEN", "AIOPS_PORTAL_READ_TOKEN",
        )
        old_env = {key: os.environ.get(key) for key in tracked_env}
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
                os.environ["AIOPS_INTERNAL_TOKEN"] = "must-not-reach-renderer"
                os.environ["AIOPS_ADMIN_TOKEN"] = "must-not-reach-renderer-either"
                os.environ["AIOPS_PORTAL_READ_TOKEN"] = "must-not-reach-renderer-either"
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
                self.assertEqual(kwargs["env"].get("PYTHONUNBUFFERED"), "1")
                self.assertEqual(kwargs["env"].get("PATH"), os.environ.get("PATH"))
                for secret_name in (
                    "AIOPS_INTERNAL_TOKEN", "AIOPS_ADMIN_TOKEN", "AIOPS_PORTAL_READ_TOKEN"
                ):
                    self.assertNotIn(secret_name, kwargs["env"])
                output = Path(args[0][-1])
                self.assertEqual(output.parent, mod.RUNS_ROOT)
                self.assertEqual(len(output.name), 32)
            finally:
                for key, value in old_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
                mod.REPO_ROOT, mod.RUNS_ROOT = old_root, old_runs
                with mod._jobs_lock:
                    mod._jobs.clear()
                    mod._recent_starts.clear()

    def test_completed_job_rejects_symlink_manifest_before_reading_target(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            output = root / "output"
            output.mkdir()
            (output / "AIOps-Demo-Complete.manifest.json").symlink_to(outside)
            job = {"process": MagicMock(), "output": output, "scenario": "SAN_FABRIC_P1",
                   "status": "running", "created_at": 1}
            job["process"].poll.return_value = 0
            result = mod._job_snapshot("c" * 32, job)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "manifest_missing_or_invalid")

    def test_completed_job_requires_manifest_and_artifact_hashes(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            video = output / "AIOps-Demo-Complete.mp4"
            subtitles = output / "AIOps-Demo-Complete.srt"
            manifest = output / "AIOps-Demo-Complete.manifest.json"
            video.write_bytes(b"fake-mp4-fixture")
            subtitles.write_text("1\\n00:00:00,000 --> 00:00:01,000\\nFixture\\n", encoding="utf-8")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            data = {
                "schema":"aiops-demo-video-manifest-v1",
                "scenario":"SAN_FABRIC_P1", "provenance":"SIMULATED_TARGET",
                "runtime_authenticated":False, "dgx_independently_attested":False,
                "live_execution_qualified":False, "live_action_authorized":False,
                "scene_count":9, "duration_target_seconds":72, "duration_actual_seconds":72.0,
                "resolution":"1920x1080", "video":video.name, "subtitles":subtitles.name,
                "video_size_bytes":video.stat().st_size, "video_sha256":digest(video),
                "subtitles_sha256":digest(subtitles)
            }
            manifest.write_text(json.dumps(data), encoding="utf-8")
            job = {"process":MagicMock(), "output":output, "scenario":"SAN_FABRIC_P1",
                   "status":"running", "created_at":1}
            job["process"].poll.return_value = 0
            result = mod._job_snapshot("a" * 32, job)
            self.assertEqual(result["status"], "completed")
            self.assertIn("video", result["artifacts"])
            # Duplicate JSON keys must not let an ambiguous manifest choose
            # different values in different parsers.
            duplicate_manifest = json.dumps(data).replace(
                '"scenario": "SAN_FABRIC_P1"',
                '"scenario": "PAYMENTS_P2", "scenario": "SAN_FABRIC_P1"',
                1,
            )
            manifest.write_text(duplicate_manifest, encoding="utf-8")
            job_duplicate = {"process":MagicMock(), "output":output, "scenario":"SAN_FABRIC_P1",
                             "status":"running", "created_at":1}
            job_duplicate["process"].poll.return_value = 0
            result_duplicate = mod._job_snapshot("d" * 32, job_duplicate)
            self.assertEqual(result_duplicate["status"], "failed")
            self.assertEqual(result_duplicate["error"], "manifest_missing_or_invalid")
            # Restore a valid manifest so the artifact tamper check remains independent.
            manifest.write_text(json.dumps(data), encoding="utf-8")
            subtitles.write_text("tampered", encoding="utf-8")
            job2 = {"process":MagicMock(), "output":output, "scenario":"SAN_FABRIC_P1",
                    "status":"running", "created_at":1}
            job2["process"].poll.return_value = 0
            result2 = mod._job_snapshot("b" * 32, job2)
            self.assertEqual(result2["status"], "failed")
            self.assertEqual(result2["error"], "manifest_or_artifact_integrity_validation_failed")
    def test_public_router_is_mounted_on_existing_portal_app(self):
        # Import in a child process so the synthetic internal token cannot leak
        # into other tests and no runtime service or listener is contacted.
        env = os.environ.copy()
        env.pop("AIOPS_ADMIN_TOKEN", None)
        env["AIOPS_INTERNAL_TOKEN"] = "synthetic-ci-only-token"
        code = (
            "import json; from portal.main import app; schema=app.openapi(); "
            "wanted={'/demo/','/demo/star','/demo/video','/demo/video/{job_id}','/demo/video/{job_id}/artifact/{artifact}'}; "
            "print(json.dumps([{'path':p,'methods':sorted(v.keys())} "
            "for p,v in schema.get('paths',{}).items() if p in wanted]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=APP_ROOT, env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        routes = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual({item["path"] for item in routes}, {"/demo/", "/demo/star", "/demo/video", "/demo/video/{job_id}", "/demo/video/{job_id}/artifact/{artifact}"})
        for item in routes:
            expected = "post" if item["path"] == "/demo/video" else "get"
            self.assertIn(expected, item["methods"])


if __name__ == "__main__":
    unittest.main()
