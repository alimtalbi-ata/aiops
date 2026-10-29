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

    def test_release_scripts_require_separate_qualification(self):
        for path in ("deploy/deploy-demo-studio-v2.sh",
                     "deploy/poll-approved-deploy.sh",
                     "deploy/install-approved-cron.sh"):
            self.write(path, "# changed release control\n")
        result = qualify(self.repo, self.stable, self.commit())
        self.assertEqual(result["assessment"], "BLOCKED")
        self.assertEqual(result["unsupported_count"], 3)
        for entry in result["module_deployment_matrix"]:
            self.assertEqual(entry["category"], "RELEASE_CONTROL_REQUALIFICATION_REQUIRED")
            self.assertEqual(entry["rollback"], "NOT_QUALIFIED")

    def test_promotion_workflow_is_not_safe_metadata(self):
        self.write(".github/workflows/promote-stable.yml", "name: unsafe\n")
        result = qualify(self.repo, self.stable, self.commit())
        self.assertEqual(result["unsupported_paths"], [".github/workflows/promote-stable.yml"])

    def test_all_github_controls_match_poller_fail_closed(self):
        # The Debian poller rejects every .github/* path, not just workflows.
        # Offline review must never label a candidate REVIEWABLE that cron blocks.
        paths = (
            ".github/CODEOWNERS",
            ".github/dependabot.yml",
            ".github/ISSUE_TEMPLATE/bug.md",
            ".github/workflows/promote-stable.yml",
        )
        for path in paths:
            self.write(path, "# changed control\\n")
        result = qualify(self.repo, self.stable, self.commit())
        self.assertEqual(result["assessment"], "BLOCKED")
        self.assertEqual(result["overall"], "NO_GO")
        self.assertEqual(result["unsupported_paths"], sorted(paths))
        matrix = {row["path"]: row for row in result["module_deployment_matrix"]}
        for path in paths:
            self.assertEqual(matrix[path]["decision"], "BLOCKED")
            self.assertEqual(matrix[path]["category"], "RELEASE_CONTROL_REQUALIFICATION_REQUIRED")
            self.assertEqual(matrix[path]["copy"], "NOT_QUALIFIED")
            self.assertEqual(matrix[path]["rollback"], "NOT_QUALIFIED")

    def test_copy_rebuild_restart_and_rollback_matrix(self):
        self.write("app/portal/demo_v2.py", "# changed\n")
        self.write("tests/test_demo_v2.py", "# changed test\n")
        result = qualify(self.repo, self.stable, self.commit())
        matrix = {row["path"]: row for row in result["module_deployment_matrix"]}
        self.assertEqual(result["assessment"], "READY_FOR_REVIEW")
        self.assertEqual(result["overall"], "NO_GO")
        self.assertEqual(matrix["app/portal/demo_v2.py"]["copy"], "COPY_TO_PORTAL_SOURCE")
        self.assertEqual(matrix["app/portal/demo_v2.py"]["rebuild"], "PORTAL_IMAGE")
        self.assertEqual(matrix["app/portal/demo_v2.py"]["restart"], "PORTAL_CONTAINER")
        self.assertEqual(matrix["tests/test_demo_v2.py"]["copy"], "COPY_TO_PORTAL_TESTS")
        self.assertEqual(matrix["tests/test_demo_v2.py"]["rebuild"], "NO_DIRECT_REBUILD")
        self.assertEqual(matrix["app/portal/demo_v2.py"]["rollback"], "SOURCE_AND_DOCKER_ROLLBACK_NOT_TESTED")
        self.assertTrue(result["matrix_is_static_contract_not_runtime_evidence"])

    def test_docs_are_not_runtime_evidence(self):
        self.write("docs/qualification.md", "offline documentation\n")
        result = qualify(self.repo, self.stable, self.commit())
        row = result["module_deployment_matrix"][0]
        self.assertEqual(row["copy"], "NO_RUNTIME_COPY")
        self.assertEqual(row["tests"], "CI_NOT_ATTESTED_HERE")
        self.assertEqual(result["field_smoke_tests"], "NOT_TESTED")

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
