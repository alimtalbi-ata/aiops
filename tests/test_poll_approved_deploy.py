import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

POLLER = Path(__file__).resolve().parents[1] / "deploy/poll-approved-deploy.sh"


def run(*args, cwd=None, env=None, check=True):
    return subprocess.run(
        list(map(str, args)),
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


class PollApprovedDeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiops-poll-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.origin = self.root / "origin.git"
        self.work = self.root / "work"
        self.base = self.root / "deploy-state"

        run("git", "init", "--bare", self.origin)
        run("git", "init", self.work)
        run("git", "config", "user.name", "AIOps Test", cwd=self.work)
        run("git", "config", "user.email", "aiops-test@example.invalid", cwd=self.work)
        run("git", "checkout", "-b", "deploy/aiops2-stable", cwd=self.work)

        script = self.work / "deploy/deploy-demo-studio-v2.sh"
        script.parent.mkdir(parents=True)
        script.write_text(
            '#!/usr/bin/env bash\n'
            'set -e\n'
            'echo invoked >> "$AIOPS_AUTODEPLOY_HOME/invocations"\n'
            'if [[ -e "$AIOPS_AUTODEPLOY_HOME/simulate-failure" ]]; then\n'
            '  exit 42\n'
            'fi\n'
        )

        demo = self.work / "app/portal/demo_v2.py"
        demo.parent.mkdir(parents=True)
        demo.write_text("# initial demo module\n")

        run("git", "add", ".", cwd=self.work)
        run("git", "commit", "-m", "initial", cwd=self.work)
        self.initial = self.sha()
        run("git", "remote", "add", "origin", self.origin, cwd=self.work)
        self.push()

        self.base.mkdir()
        # Keep the production poller unmodified. A test-only git executable
        # maps ONLY the approved GitHub clone URL to the ephemeral bare repo;
        # subsequent fetches use that local origin. The production script has
        # no test-mode or remote-override bypass.
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        shim = bin_dir / "git"
        shim.write_text(
            '#!/usr/bin/env bash\n'
            'if [[ "$1" == clone && "$2" == --filter=blob:none && '
            '( "$3" == git@github.com:alimtalbi-ata/aiops.git || '
            '"$3" == https://github.com/alimtalbi-ata/aiops.git ) ]]; then\n'
            f'  exec {shlex.quote(real_git)} clone --filter=blob:none "$AIOPS_TEST_ORIGIN" "$4"\n'
            'fi\n'
            f'exec {shlex.quote(real_git)} "$@"\n'
        )
        shim.chmod(0o700)
        self.env = os.environ.copy()
        self.env.pop("AIOPS_DEPLOY_REMOTE", None)
        self.env.update({
            "AIOPS_AUTODEPLOY_HOME": str(self.base),
            "AIOPS_TEST_ORIGIN": str(self.origin),
            "AIOPS_DEPLOY_BRANCH": "deploy/aiops2-stable",
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "GIT_TERMINAL_PROMPT": "0",
        })

    def sha(self):
        return run("git", "rev-parse", "HEAD", cwd=self.work).stdout.strip()

    def push(self, force=False):
        args = ["git", "push"]
        if force:
            args.append("--force")
        args.extend(["origin", "HEAD:refs/heads/deploy/aiops2-stable"])
        run(*args, cwd=self.work)

    def advance(self, message):
        f = self.work / "app/portal/demo_v2.py"
        f.write_text("# " + message + "\n")
        run("git", "add", ".", cwd=self.work)
        run("git", "commit", "-m", message, cwd=self.work)
        self.push()
        return self.sha()

    def poll(self):
        return run("bash", POLLER, env=self.env, check=False)

    def write_applied(self, sha):
        (self.base / "applied.sha").write_text(sha + "\n")

    def invocations(self):
        p = self.base / "invocations"
        return p.read_text().splitlines() if p.exists() else []

    def test_poller_rejects_nonstable_refs_before_git_or_deployment(self):
        # The installer is not the security boundary: the cron script may be
        # invoked directly with a modified environment.
        self.write_applied(self.initial)
        for branch in ("feat/unreviewed", "main",
                       "refs/heads/deploy/aiops2-stable",
                       "deploy/aiops2-stable ", " "):
            with self.subTest(branch=branch):
                env = dict(self.env, AIOPS_DEPLOY_BRANCH=branch)
                result = run("bash", POLLER, env=env, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("poller only accepts deploy/aiops2-stable",
                              result.stderr)
                self.assertFalse((self.base / "repo").exists())
                self.assertFalse((self.base / "poll.lock").exists())
                self.assertEqual(self.invocations(), [])
                self.assertEqual((self.base / "applied.sha").read_text(),
                                 self.initial + "\n")

    def test_poller_rejects_unapproved_remote_before_git_or_deployment(self):
        self.write_applied(self.initial)
        for remote in (str(self.origin), "file:///tmp/unreviewed.git",
                       "git@github.com:attacker/aiops.git",
                       "https://github.com/alimtalbi-ata/aiops",
                       "https://evil.example/alimtalbi-ata/aiops.git",
                       " https://github.com/alimtalbi-ata/aiops.git"):
            with self.subTest(remote=remote):
                env = dict(self.env, AIOPS_DEPLOY_REMOTE=remote)
                result = run("bash", POLLER, env=env, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("remote must be the approved GitHub repository",
                              result.stderr)
                self.assertFalse((self.base / "repo").exists())
                self.assertFalse((self.base / "poll.lock").exists())
                self.assertEqual(self.invocations(), [])
                self.assertEqual((self.base / "applied.sha").read_text(),
                                 self.initial + "\n")

    def test_approved_https_remote_deploys_from_ephemeral_git_fixture(self):
        self.write_applied(self.initial)
        target = self.advance("approved HTTPS candidate")
        env = dict(self.env, AIOPS_DEPLOY_REMOTE="https://github.com/alimtalbi-ata/aiops.git")
        result = run("bash", POLLER, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.invocations(), ["invoked"])
        self.assertEqual((self.base / "applied.sha").read_text().strip(), target)

    def test_already_applied(self):
        self.write_applied(self.initial)
        result = self.poll()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.invocations(), [])

    def test_quarantined_sha(self):
        self.write_applied(self.initial)
        target = self.advance("candidate")
        (self.base / "failed.sha").write_text(target + "\n")
        result = self.poll()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.invocations(), [])
        self.assertEqual((self.base / "applied.sha").read_text().strip(), self.initial)

    def test_non_fast_forward(self):
        self.write_applied(self.initial)
        self.advance("candidate")
        run("git", "checkout", "--orphan", "replacement", cwd=self.work)
        run("git", "rm", "-rf", ".", cwd=self.work)
        script = self.work / "deploy/deploy-demo-studio-v2.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("#!/usr/bin/env bash\nexit 0\n")
        run("git", "add", ".", cwd=self.work)
        run("git", "commit", "-m", "unrelated history", cwd=self.work)
        self.push(force=True)
        result = self.poll()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.invocations(), [])
        self.assertEqual((self.base / "applied.sha").read_text().strip(), self.initial)

    def test_failed_deployment(self):
        self.write_applied(self.initial)
        target = self.advance("candidate")
        (self.base / "simulate-failure").touch()
        result = self.poll()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.invocations(), ["invoked"])
        self.assertEqual((self.base / "failed.sha").read_text().strip(), target)
        self.assertEqual((self.base / "applied.sha").read_text().strip(), self.initial)

        second = self.poll()
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(self.invocations(), ["invoked"])

    def test_missing_applied_sha_never_bootstraps(self):
        self.advance("candidate")
        result = self.poll()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manual bootstrap required", result.stderr)
        self.assertEqual(self.invocations(), [])
        self.assertFalse((self.base / "applied.sha").exists())

    def test_changed_core_module_blocks_before_deployer(self):
        self.write_applied(self.initial)
        self.advance("candidate")
        core = self.work / "app/core/main.py"
        core.parent.mkdir(parents=True, exist_ok=True)
        core.write_text("# undeployed Core change\n")
        run("git", "add", ".", cwd=self.work)
        run("git", "commit", "-m", "uncovered Core change", cwd=self.work)
        self.push()
        result = self.poll()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not transported", result.stderr)
        self.assertEqual(self.invocations(), [])
        self.assertEqual((self.base / "applied.sha").read_text().strip(), self.initial)

    def test_changed_deployer_blocks_automatic_rollout(self):
        self.write_applied(self.initial)
        self.advance("candidate")
        script = self.work / "deploy/deploy-demo-studio-v2.sh"
        script.write_text(script.read_text() + "# changed deployer\n")
        run("git", "add", ".", cwd=self.work)
        run("git", "commit", "-m", "changed deployer", cwd=self.work)
        self.push()
        result = self.poll()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not transported", result.stderr)
        self.assertEqual(self.invocations(), [])

    def test_deleted_deployed_module_blocks(self):
        self.write_applied(self.initial)
        (self.work / "app/portal/demo_v2.py").unlink()
        run("git", "add", "-A", cwd=self.work)
        run("git", "commit", "-m", "deleted demo module", cwd=self.work)
        self.push()
        result = self.poll()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe candidate diff status", result.stderr)
        self.assertEqual(self.invocations(), [])

    def test_successful_deployment(self):
        self.write_applied(self.initial)
        target = self.advance("candidate")
        result = self.poll()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.invocations(), ["invoked"])
        self.assertEqual((self.base / "applied.sha").read_text().strip(), target)


if __name__ == "__main__":
    unittest.main()
