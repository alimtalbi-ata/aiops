#!/usr/bin/env python3
"""Offline preflight command-boundary regression checks; synthetic, not host E2E."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import portal_candidate_preflight as preflight


class PreflightCommandBoundary(unittest.TestCase):
    def test_commands_only_run_declared_repository_tests(self):
        root = preflight.ROOT
        self.assertTrue((root / "scripts/fs/tests/portal_candidate_preflight.py").is_file())
        self.assertEqual(len({name for name, _ in preflight.GATES}), len(preflight.GATES))
        for name, argv in preflight.GATES:
            with self.subTest(gate=name):
                self.assertIsInstance(name, str)
                self.assertTrue(name)
                self.assertIsInstance(argv, list)
                self.assertGreater(len(argv), 1)
                self.assertTrue(all(isinstance(arg, str) and arg for arg in argv))
                self.assertIn(argv[0], ("python3", "node"))
                self.assertNotIn("-c", argv)
                self.assertNotIn("-e", argv)
                self.assertNotIn("--eval", argv)
                self.assertNotIn("--import", argv)
                self.assertNotIn("--require", argv)
                self.assertNotIn("--loader", argv)
                self.assertNotIn("--experimental-loader", argv)
                self.assertNotIn("--inspect", argv)
                self.assertNotIn("--inspect-brk", argv)
                self.assertNotIn("-m", argv) if argv[0] == "node" else None
                for arg in argv[1:]:
                    self.assertNotIn("://", arg)
                    self.assertFalse(arg.startswith(("/", "~")))
                    self.assertNotIn("..", pathlib.PurePosixPath(arg).parts)
                    self.assertNotIn("\\x00", arg)
                paths = [arg for arg in argv if arg.endswith((".py", ".mjs"))]
                self.assertTrue(paths, "gate must name a test file")
                for path in paths:
                    self.assertTrue(path.startswith(("scripts/fs/tests/", "app/portal/components/", "tests/")))
                    self.assertTrue((root / path).is_file(), path)

    def test_no_runtime_or_deployment_entrypoints(self):
        forbidden = {"docker", "compose", "kubectl", "ssh", "scp", "curl", "wget",
                     "sudo", "systemctl", "npm", "npx", "pip", "bash", "sh",
                     "git", "deploy", "restart", "build", "cron", "crontab"}
        for name, argv in preflight.GATES:
            with self.subTest(gate=name):
                self.assertFalse(forbidden.intersection(argv))
                self.assertNotIn("--", argv)
                self.assertNotIn("--collect-only", argv)
                self.assertNotIn("--update-snapshots", argv)


if __name__ == "__main__":
    unittest.main()
