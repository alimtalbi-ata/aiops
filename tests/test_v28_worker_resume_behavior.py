import ast
import pathlib
import unittest

SRC = pathlib.Path(__file__).resolve().parents[1] / "app/worker/main.py"

class AtomicDenialBlockError(Exception):
    pass

class WorkerResumeTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SRC.read_text())
        fn = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and n.name == "recover_committed_critic_block"
        )
        self.status = "RUNNING"
        self.version = 3
        self.completed = True
        self.posts = []
        self.fail_resume = False
        self.intel_calls = 0

        def get_json(base, path, token=None):
            if path.endswith("/critic-denial-block/receipt"):
                return {
                    "run_id": "RUN-179",
                    "status": "BLOCKED",
                    "denial_hash": "a" * 64,
                    "critique_id": "CRT-179",
                    "analysis_id": "ANL-179",
                    "outbox_status": "PENDING",
                    "current_version": self.version,
                    "version": 4,
                }
            if path == "/api/runs/RUN-179":
                events = [{
                    "stage": "DGX_CRITIC",
                    "event_type": "CRITIC_COMPLETED",
                }] if self.completed else []
                return {
                    "run": {
                        "status": self.status,
                        "version": self.version,
                    },
                    "events": events,
                }
            raise AssertionError("unexpected_get: " + path)

        def post_json(base, path, payload, timeout=None, token=None):
            self.posts.append(path)
            if self.fail_resume:
                raise ConnectionError("simulated_http_failure")
            if path != "/api/runs/RUN-179/critic-denial-resume":
                raise AssertionError("unexpected_post: " + path)
            self.status = "BLOCKED"
            self.version = 4
            return {
                "run_id": "RUN-179",
                "status": "BLOCKED",
                "version": 4,
                "denial_hash": "a" * 64,
            }

        ns = {
            "get_json": get_json,
            "post_json": post_json,
            "AtomicDenialBlockError": AtomicDenialBlockError,
            "CORE": "mock-core",
            "ADMIN": "test-token",
        }
        exec(
            compile(ast.Module(body=[fn], type_ignores=[]), str(SRC), "exec"),
            ns,
        )
        self.recover = ns["recover_committed_critic_block"]

    def test_running_completed_resumes_without_ai(self):
        result = self.recover("RUN-179")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["recovered_from_receipt"])
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.intel_calls, 0)

    def test_committed_block_uses_receipt(self):
        self.status = "BLOCKED"
        self.version = 4
        result = self.recover("RUN-179")
        self.assertEqual(result["version"], 4)
        self.assertEqual(self.posts, [])

    def test_running_without_completed_event(self):
        self.completed = False
        self.assertIsNone(self.recover("RUN-179"))
        self.assertEqual(self.posts, [])

    def test_resume_http_error_fails_closed(self):
        self.fail_resume = True
        with self.assertRaises(AtomicDenialBlockError) as error:
            self.recover("RUN-179")
        self.assertIn("critic_durable_resume_unconfirmed", str(error.exception))
        self.assertEqual(len(self.posts), 1)

    def test_invalid_terminal_state_fails_closed(self):
        self.status = "CANCELLED"
        with self.assertRaises(AtomicDenialBlockError):
            self.recover("RUN-179")
        self.assertEqual(self.posts, [])

if __name__ == "__main__":
    unittest.main()
