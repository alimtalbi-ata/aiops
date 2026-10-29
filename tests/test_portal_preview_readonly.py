"""Offline preview boundary tests: no actual Core/GLPI/Policy runtime claim."""
import unittest

from scripts.check_demo_portal_preview import ReadOnlyPreview, isolate_environment


class PortalPreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_post_and_put_refused_before_downstream(self):
        called = []
        async def downstream(scope, receive, send):
            called.append(scope)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = []
            async def send(message):
                sent.append(message)
            await ReadOnlyPreview(downstream)(
                {"type": "http", "method": method, "path": "/api/demo"}, None, send)
            self.assertEqual(sent[0]["status"], 405)
            self.assertEqual(sent[1]["body"], b"read-only preview")
        self.assertEqual(called, [])

    async def test_get_passes_through_without_mutation(self):
        called = []
        async def downstream(scope, receive, send):
            called.append(scope["path"])
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"existing portal"})
        sent = []
        async def send(message):
            sent.append(message)
        await ReadOnlyPreview(downstream)(
            {"type": "http", "method": "GET", "path": "/demo-studio/business-story"},
            None, send)
        self.assertEqual(called, ["/demo-studio/business-story"])
        self.assertEqual(sent[0]["status"], 200)

    async def test_websocket_refused(self):
        called = []
        async def downstream(scope, receive, send):
            called.append(True)
        sent = []
        async def send(message):
            sent.append(message)
        await ReadOnlyPreview(downstream)({"type": "websocket"}, None, send)
        self.assertEqual(sent, [{"type": "websocket.close", "code": 1008}])
        self.assertEqual(called, [])

    async def test_env_isolation_overrides_existing_credentials(self):
        env = {"AIOPS_INTERNAL_TOKEN": "live-credential",
               "AIOPS_ADMIN_TOKEN": "live-admin", "AIOPS_DEMO_LAUNCH_ENABLED": "true",
               "CORE_URL": "https://production.example", "TWIN_URL": "https://production.example"}
        isolate_environment(env)
        self.assertNotEqual(env["AIOPS_INTERNAL_TOKEN"], "live-credential")
        self.assertNotIn("AIOPS_ADMIN_TOKEN", env)
        self.assertEqual(env["AIOPS_DEMO_LAUNCH_ENABLED"], "false")
        for name in ("CORE_URL", "TWIN_URL", "COPILOT_URL"):
            self.assertEqual(env[name], "http://127.0.0.1:1")


if __name__ == "__main__":
    unittest.main()
