"""Offline, non-Docker contract tests for the fail-closed cron installer."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / "deploy/install-approved-cron.sh"


def run(*args, cwd=None, env=None, check=True):
    return subprocess.run(
        [str(a) for a in args], cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


class InstallApprovedCronTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aiops-cron-install-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.origin = self.root / "origin.git"
        self.work = self.root / "work"
        self.base = self.root / "state"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.base.mkdir()
        run("git", "init", "--bare", self.origin)
        run("git", "init", self.work)
        run("git", "config", "user.name", "AIOps CI", cwd=self.work)
        run("git", "config", "user.email", "aiops-ci@example.invalid", cwd=self.work)
        run("git", "checkout", "-b", "deploy/aiops2-stable", cwd=self.work)
        (self.work / "README.md").write_text("initial\n")
        run("git", "add", ".", cwd=self.work)
        run("git", "commit", "-m", "initial", cwd=self.work)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.work).stdout.strip()
        run("git", "remote", "add", "origin", self.origin, cwd=self.work)
        run("git", "push", "origin", "HEAD:refs/heads/deploy/aiops2-stable", cwd=self.work)
        run("git", "clone", self.origin, self.base / "repo")
        # A mock crontab only: no host crontab or Docker is ever invoked.
        crontab = self.bin / "crontab"
        crontab.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = "-l" ]; then\n'
            '  [ ! -f "$AIOPS_TEST_CRONTAB" ] || cat "$AIOPS_TEST_CRONTAB"\n'
            'else\n'
            '  cat > "$AIOPS_TEST_CRONTAB"\n'
            'fi\n'
        )
        crontab.chmod(0o700)
        self.env = os.environ.copy()
        self.env.update({
            "AIOPS_AUTODEPLOY_HOME": str(self.base),
            "AIOPS_TEST_CRONTAB": str(self.root / "crontab.txt"),
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "GIT_TERMINAL_PROMPT": "0",
        })
        self.assertTrue((INSTALLER.parent / "poll-approved-deploy.sh").is_file())

    def install(self, env=None):
        return run("bash", INSTALLER, env=env or self.env, check=False)

    def assert_no_schedule(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / "crontab.txt").exists())
        self.assertFalse((self.base / "poll.sh").exists())

    def test_missing_applied_sha_cannot_be_invented_from_git_target(self):
        result = self.install()
        self.assert_no_schedule(result)
        self.assertIn("no automatic bootstrap", result.stderr)
        self.assertFalse((self.base / "applied.sha").exists())

    def test_symlink_is_rejected(self):
        actual = self.root / "external-sha"
        actual.write_text(self.sha + "\n")
        (self.base / "applied.sha").symlink_to(actual)
        self.assert_no_schedule(self.install())

    def test_invalid_applied_sha_is_rejected(self):
        (self.base / "applied.sha").write_text("0" * 40 + "\n")
        self.assert_no_schedule(self.install())

    def test_extra_lines_are_rejected(self):
        (self.base / "applied.sha").write_text(self.sha + "\n\n")
        self.assert_no_schedule(self.install())

    def test_stale_applied_sha_blocks_automatic_rollout(self):
        (self.base / "applied.sha").write_text(self.sha + "\n")
        (self.work / "README.md").write_text("candidate\n")
        run("git", "add", ".", cwd=self.work)
        run("git", "commit", "-m", "candidate", cwd=self.work)
        run("git", "push", "origin", "HEAD:refs/heads/deploy/aiops2-stable", cwd=self.work)
        result = self.install()
        self.assert_no_schedule(result)
        self.assertIn("manual release review required", result.stderr)
        self.assertEqual((self.base / "applied.sha").read_text(), self.sha + "\n")

    def test_only_stable_branch_is_accepted(self):
        env = dict(self.env, AIOPS_DEPLOY_BRANCH="feat/unreviewed")
        self.assert_no_schedule(self.install(env))

    def test_matching_operator_file_schedules_without_mutation(self):
        (self.base / "applied.sha").write_text(self.sha + "\n")
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NOT_ATTESTED", result.stdout)
        self.assertEqual((self.base / "applied.sha").read_text(), self.sha + "\n")
        self.assertIn("*/5 * * * *", (self.root / "crontab.txt").read_text())
        self.assertTrue((self.base / "poll.sh").is_file())


if __name__ == "__main__":
    unittest.main()
