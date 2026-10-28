"""Real local Git history tests; no mocks, network, production, or deploy."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_demo_stable_coverage import Blocked, qualify


def run(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


class StableCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aiops-stable-coverage-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        run(self.repo, "init", "-q", "-b", "master")
        run(self.repo, "config", "user.email", "ci@example.invalid")
        run(self.repo, "config", "user.name", "CI")
        self.write("app/portal/demo_v2.py", "# demo\n")
        self.write("deploy/deploy-demo-studio-v2.sh", "#!/bin/sh\n")
        self.write("tests/test_demo_v2.py", "# test\n")
        self.stable = self.commit()

    def write(self, name: str, content: str):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit(self) -> str:
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-qm", "test")
        return run(self.repo, "rev-parse", "HEAD")

    def test_only_deployed_module_is_reviewable_not_go(self):
        self.write("app/portal/demo_v2.py", "# new demo\n")
        head = self.commit()
        result = qualify(self.repo, self.stable, head)
        self.assertEqual(result["assessment"], "READY_FOR_REVIEW")
        self.assertEqual(result["overall"], "NO_GO")
        self.assertEqual(result["field_smoke_tests"], "NOT_TESTED")

    def test_core_change_is_blocked_even_with_portal_change(self):
        self.write("app/portal/demo_v2.py", "# new demo\n")
        self.write("app/core/main.py", "# not deployed\n")
        result = qualify(self.repo, self.stable, self.commit())
        self.assertEqual(result["assessment"], "BLOCKED")
        self.assertEqual(result["unsupported_paths"], ["app/core/main.py"])

    def test_portal_main_injection_is_not_full_file_deployment(self):
        self.write("app/portal/main.py", "# new API\n")
        result = qualify(self.repo, self.stable, self.commit())
        self.assertIn("app/portal/main.py", result["unsupported_paths"])

    def test_deleted_copied_file_is_blocked(self):
        (self.repo / "app/portal/demo_v2.py").unlink()
        with self.assertRaisesRegex(Blocked, "git_ref_or_history_unavailable"):
            qualify(self.repo, self.stable, self.commit())

    def test_diverged_history_is_blocked(self):
        run(self.repo, "checkout", "-qb", "other", self.stable)
        self.write("docs/other.md", "other\n")
        other = self.commit()
        run(self.repo, "checkout", "-q", "master")
        self.write("docs/current.md", "current\n")
        current = self.commit()
        with self.assertRaisesRegex(Blocked, "non_fast_forward_or_diverged"):
            qualify(self.repo, other, current)

    def test_untrusted_sha_and_noop_are_blocked(self):
        with self.assertRaisesRegex(Blocked, "invalid_sha"):
            qualify(self.repo, "main;rm -rf /", self.stable)
        with self.assertRaisesRegex(Blocked, "no_new_candidate"):
            qualify(self.repo, self.stable, self.stable)

    def test_undeployed_twin_and_schema_changes_are_blocked(self):
        self.write("app/twin/main.py", "# impact\n")
        self.write("db/migrations/006_impact.sql", "-- schema\n")
        result = qualify(self.repo, self.stable, self.commit())
        self.assertEqual(result["unsupported_count"], 2)


if __name__ == "__main__":
    unittest.main()
