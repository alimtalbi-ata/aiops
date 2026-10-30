"""P0 deployer contract tests: disposable Git and mocked Docker, never a host rollout."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/deploy-acme-p0.py"
spec = importlib.util.spec_from_file_location("deploy_acme_p0", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


class DeployAcmeP0Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aiops-p0-transaction-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.delivery = self.root / "delivery"
        self.delivery.mkdir()
        git(self.delivery, "init", "-q")
        git(self.delivery, "config", "user.name", "CI")
        git(self.delivery, "config", "user.email", "ci@example.invalid")
        (self.delivery / "README.md").write_text("stable\n")
        git(self.delivery, "add", "-A")
        git(self.delivery, "commit", "-qm", "stable")
        self.stable = git(self.delivery, "rev-parse", "HEAD")

    def candidate(self, path="app/core/main.py"):
        file = self.delivery / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("# qualified candidate\n")
        git(self.delivery, "add", "-A")
        git(self.delivery, "commit", "-qm", "candidate")
        return git(self.delivery, "rev-parse", "HEAD")

    def test_transport_contract_is_explicit(self):
        for path in module.RUNTIME:
            self.assertEqual(module.classify(path, "M"), "IMAGE_TRANSPORT")
        self.assertEqual(module.classify("compose.yml", "M"),
                         "LIVE_COMPOSE_COMPATIBILITY_REQUIRED")
        self.assertEqual(module.classify(".github/workflows/quality.yml", "M"),
                         "MANUAL_RELEASE_CONTROL_REVIEW")
        self.assertEqual(module.classify("deploy/deploy-acme-p0.py", "A"),
                         "MANUAL_RELEASE_CONTROL_REVIEW")
        for path in ("app/worker/main.py", "app/copilot/main.py",
                     "db/migrations/999.sql", ".github/dependabot.yml",
                     "deploy/unknown.sh", "config/secrets.env"):
            self.assertEqual(module.classify(path, "M"), "BLOCKED")
        self.assertEqual(module.classify("app/core/main.py", "D"), "BLOCKED")

    def test_cross_lot_transport_matrix_stays_explicit_and_fail_closed(self):
        for path in (
            "app/shared/acme_demo_offline.py", "app/shared/acme_glpi_ticket_read.py",
            "app/shared/acme_itsm_evidence_link.py", "app/shared/acme_policy_demo_result.py",
            "app/shared/acme_remediation_projection.py",
            "app/shared/acme_remediation_receipt.py", "app/shared/remediation_lab.py",
        ):
            self.assertEqual(module.classify(path, "A"), "IMAGE_TRANSPORT")
        for path in module.OPERATOR_ONLY:
            self.assertEqual(module.classify(path, "A"), "CI_OR_OPERATOR_ONLY")
        for path in ("app/shared/unknown_module.py", "tools/unknown.py",
                     "config/remediation/unsafe.json"):
            self.assertEqual(module.classify(path, "A"), "BLOCKED")

        for path in (*module.OPERATOR_ONLY, "app/shared/acme_glpi_ticket_read.py"):
            file = self.delivery / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("# candidate\n")
        git(self.delivery, "add", "-A")
        git(self.delivery, "commit", "-qm", "cross-lot")
        candidate = git(self.delivery, "rev-parse", "HEAD")
        result = module.plan(self.delivery, self.stable, candidate)
        self.assertEqual(result["assessment"], "MANUAL_APPROVAL_REQUIRED")
        self.assertEqual(result["overall"], "NO_GO")
        self.assertEqual(result["unsupported_paths"], [])
        self.assertEqual(result["not_image_transported"], sorted(module.OPERATOR_ONLY))

    def test_git_plan_never_claims_go_or_debian(self):
        candidate = self.candidate()
        result = module.plan(self.delivery, self.stable, candidate)
        self.assertEqual(result["assessment"], "MANUAL_APPROVAL_REQUIRED")
        self.assertEqual(result["overall"], "NO_GO")
        self.assertEqual(result["live_host"], "NOT_TESTED")
        self.assertEqual(result["rollback"], "NOT_TESTED")
        self.assertEqual(result["applied_sha"], "NOT_ATTESTED")
        self.assertEqual(result["module_deployment_matrix"][0]["transport"],
                         "IMAGE_TRANSPORT")

    def test_uncovered_application_change_blocks(self):
        candidate = self.candidate("app/worker/main.py")
        result = module.plan(self.delivery, self.stable, candidate)
        self.assertEqual(result["assessment"], "BLOCKED")
        self.assertEqual(result["unsupported_paths"], ["app/worker/main.py"])

    def test_dirty_checkout_refused_before_docker(self):
        candidate = self.candidate()
        (self.delivery / "untracked").write_text("do not overwrite\n")
        with self.assertRaisesRegex(module.Refused, "dirty_delivery_checkout"):
            module.plan(self.delivery, self.stable, candidate)

    def test_invalid_sha_refused(self):
        candidate = self.candidate()
        with self.assertRaisesRegex(module.Refused, "invalid_release_shas"):
            module.plan(self.delivery, "main", candidate)

    def test_rootless_guard_refuses_unknown_engine_without_calling_docker(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "unix:///var/run/docker.sock",
                                      "XDG_RUNTIME_DIR": "/run/user/1001"}):
            with patch.object(module, "command") as cmd:
                with self.assertRaisesRegex(module.Refused, "unqualified_docker_socket"):
                    module.docker_guard()
                cmd.assert_not_called()

    def test_override_does_not_accept_injected_image_names(self):
        target = self.root / "override.yml"
        with self.assertRaises(module.Refused):
            module.write_override(target, {k: "ok;rm -rf /" for k in module.SERVICES})
        self.assertFalse(target.exists())

    def test_operator_approval_required_before_host_io(self):
        candidate = self.candidate()
        with patch.object(module, "apply") as do_apply:
            result = module.main(["--delivery", str(self.delivery),
                                  "--stable-sha", self.stable,
                                  "--candidate-sha", candidate, "--apply",
                                  "--source-dir", str(self.delivery)])
        self.assertEqual(result, 2)
        do_apply.assert_not_called()

    def _state(self):
        state = self.root / "state"
        state.mkdir()
        (state / "applied.sha").write_text(self.stable + "\n")
        return state

    def _originals(self):
        return {k: "sha256:" + ("a" * 64) for k in module.SERVICES}

    def test_targeted_rollout_rollback_on_compose_failure(self):
        state = self._state()
        source = self.root / "source"
        source.mkdir()
        calls = []

        def fake_command(*args, **kwargs):
            calls.append(args)
            if "up" in args and any("candidate.yml" in str(x) for x in args):
                raise module.Refused("simulated_compose_failure")
            return ""

        with patch.object(module, "preflight_host", return_value=self._originals()), \
             patch.object(module, "command", side_effect=fake_command), \
             patch.object(module, "inspect_owned", return_value=self._originals()), \
             patch.object(module, "wait_healthy"):
            with self.assertRaisesRegex(module.Refused, "deployment_failed_original_images_preserved"):
                module.apply(self.delivery, source, state, "b" * 40, self.stable)
        self.assertTrue(any("up" in x and any("rollback.yml" in str(y) for y in x)
                            for x in calls))
        self.assertEqual((state / "applied.sha").read_text(), self.stable + "\n")
        self.assertFalse((state / "DEPLOYMENT_BLOCKED").exists())

    def test_incomplete_rollback_quarantines(self):
        state = self._state()
        source = self.root / "source"
        source.mkdir()

        def fail_up(*args, **kwargs):
            if "up" in args:
                raise module.Refused("simulated_failure")
            return ""

        with patch.object(module, "preflight_host", return_value=self._originals()), \
             patch.object(module, "command", side_effect=fail_up), \
             patch.object(module, "inspect_owned", return_value=self._originals()), \
             patch.object(module, "wait_healthy"):
            with self.assertRaisesRegex(module.Refused, "rollback_incomplete"):
                module.apply(self.delivery, source, state, "b" * 40, self.stable)
        self.assertTrue((state / "DEPLOYMENT_BLOCKED").exists())
        self.assertEqual((state / "applied.sha").read_text(), self.stable + "\n")

    def test_existing_block_marker_refuses_before_docker(self):
        state = self._state()
        (state / "DEPLOYMENT_BLOCKED").write_text("rollback failed\\n")
        with patch.object(module, "preflight_host") as preflight:
            with self.assertRaisesRegex(module.Refused, "existing_deployment_block_marker"):
                module.apply(self.delivery, self.root, state, "b" * 40, self.stable)
            preflight.assert_not_called()

    def test_mismatched_applied_sha_refuses_before_docker(self):
        state = self._state()
        (state / "applied.sha").write_text("a" * 40 + "\n")
        with patch.object(module, "preflight_host") as preflight:
            with self.assertRaisesRegex(module.Refused, "applied_sha_not_matching_approved_stable"):
                module.apply(self.delivery, self.root, state, "b" * 40, self.stable)
            preflight.assert_not_called()

    def test_symlink_applied_sha_refused(self):
        state = self._state()
        (state / "applied.sha").unlink()
        (state / "applied.sha").symlink_to(self.delivery / "README.md")
        with patch.object(module, "preflight_host") as preflight:
            with self.assertRaisesRegex(module.Refused, "missing_existing_operator_release_state"):
                module.apply(self.delivery, self.root, state, "b" * 40, self.stable)
            preflight.assert_not_called()

    def test_readonly_host_inspection_checks_ownership_without_apply(self):
        candidate = self.candidate()
        state = self._state()
        source = self.root / "source"
        source.mkdir()
        out = io.StringIO()
        with patch.object(module, "preflight_host", return_value=self._originals()) as inspect, \
             patch.object(module, "apply") as apply, \
             patch("sys.stdout", out):
            code = module.main(["--delivery", str(self.delivery),
                                "--stable-sha", self.stable, "--candidate-sha", candidate,
                                "--source-dir", str(source), "--state-dir", str(state),
                                "--inspect-host"])
        self.assertEqual(code, 0)
        inspect.assert_called_once_with(source)
        apply.assert_not_called()
        receipt = json.loads(out.getvalue())
        self.assertEqual(receipt["assessment"], "HOST_PREFLIGHT_PASS_UNATTESTED")
        self.assertEqual(receipt["overall"], "NO_GO")
        self.assertEqual(receipt["poller_migration"], "NOT_TESTED")
        self.assertEqual(receipt["e2e"], "NOT_TESTED")
        self.assertEqual((state / "applied.sha").read_text(), self.stable + "\n")

    def test_readonly_host_inspection_refuses_stale_state_before_docker(self):
        candidate = self.candidate()
        state = self._state()
        (state / "applied.sha").write_text("a" * 40 + "\n")
        source = self.root / "source"
        source.mkdir()
        out = io.StringIO()
        with patch.object(module, "preflight_host") as inspect, \
             patch.object(module, "apply") as apply, \
             patch("sys.stdout", out):
            code = module.main(["--delivery", str(self.delivery),
                                "--stable-sha", self.stable, "--candidate-sha", candidate,
                                "--source-dir", str(source), "--state-dir", str(state),
                                "--inspect-host"])
        self.assertEqual(code, 2)
        inspect.assert_not_called()
        apply.assert_not_called()
        self.assertEqual(json.loads(out.getvalue())["overall"], "NO_GO")

    def test_success_is_unattested_and_preserves_applied_sha(self):
        state = self._state()
        source = self.root / "source"
        source.mkdir()
        expected = {k: "sha256:" + "b" * 64 for k in module.SERVICES}
        def success_command(*args, **kwargs):
            if len(args) >= 4 and args[:3] == ("docker", "image", "inspect"):
                return json.dumps("sha256:" + "b" * 64)
            return ""
        with patch.object(module, "preflight_host", return_value=self._originals()), \
             patch.object(module, "command", side_effect=success_command), \
             patch.object(module, "inspect_owned", return_value=expected), \
             patch.object(module, "wait_healthy"):
            receipt = module.apply(self.delivery, source, state, "b" * 40, self.stable)
        self.assertEqual(receipt["assessment"], "APPLIED_UNATTESTED")
        self.assertEqual(receipt["overall"], "NO_GO")
        self.assertEqual(receipt["e2e"], "NOT_TESTED")
        self.assertEqual(receipt["rollback_exercised"], "NOT_TESTED")
        self.assertEqual((state / "applied.sha").read_text(), self.stable + "\n")


if __name__ == "__main__":
    unittest.main()
