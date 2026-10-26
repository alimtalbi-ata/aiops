"""Offline regression tests for the bounded Docker BuildKit retry helper."""
from __future__ import annotations

import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ci_docker_build


class DockerBuildRetryTests(unittest.TestCase):
    @staticmethod
    def result(code: int, *, stdout: str = "", stderr: str = ""):
        return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)

    def test_recognized_buildkit_eof_retries_once_and_preserves_success(self):
        runner = Mock(side_effect=[
            self.result(1, stderr="target aiops2-copilot: failed to receive status: rpc error: code = Unavailable desc = error reading from server: EOF\n"),
            self.result(0, stdout="build complete\n"),
        ])
        sleeper = Mock()
        out, err = io.StringIO(), io.StringIO()
        code = ci_docker_build.run_compose(
            ["--env-file", ".env", "build"], runner=runner, sleeper=sleeper,
            stdout=out, stderr=err,
        )
        self.assertEqual(code, 0)
        self.assertEqual(runner.call_count, 2)
        expected = ["docker", "compose", "--env-file", ".env", "build"]
        self.assertEqual(runner.call_args_list[0].args[0], expected)
        self.assertEqual(runner.call_args_list[1].args[0], expected)
        sleeper.assert_called_once_with(2)
        self.assertIn("retrying once", err.getvalue())
        self.assertIn("build complete", out.getvalue())

    def test_non_transient_build_failure_is_not_retried(self):
        runner = Mock(return_value=self.result(17, stderr="failed to solve: Dockerfile parse error"))
        code = ci_docker_build.run_compose(
            ["build"], runner=runner, sleeper=Mock(),
            stdout=io.StringIO(), stderr=io.StringIO(),
        )
        self.assertEqual(code, 17)
        runner.assert_called_once()

    def test_repeated_transient_failure_stays_failed_after_one_retry(self):
        transient = "rpc error: code = Unavailable desc = transport is closing"
        runner = Mock(side_effect=[self.result(1, stderr=transient), self.result(1, stderr=transient)])
        sleeper = Mock()
        code = ci_docker_build.run_compose(
            ["build"], runner=runner, sleeper=sleeper,
            stdout=io.StringIO(), stderr=io.StringIO(),
        )
        self.assertEqual(code, 1)
        self.assertEqual(runner.call_count, 2)
        sleeper.assert_called_once_with(2)

    def test_unexpected_eof_is_recognized_but_generic_errors_are_not(self):
        self.assertTrue(ci_docker_build.is_transient_transport_failure("failed to solve: unexpected EOF"))
        self.assertFalse(ci_docker_build.is_transient_transport_failure("Dockerfile parse error"))
        self.assertFalse(ci_docker_build.is_transient_transport_failure("401 Unauthorized"))

    def test_empty_arguments_do_not_launch_docker(self):
        runner = Mock()
        err = io.StringIO()
        code = ci_docker_build.run_compose([], runner=runner, stderr=err)
        self.assertEqual(code, 2)
        runner.assert_not_called()
        self.assertIn("usage:", err.getvalue())

    def test_missing_docker_binary_returns_stable_error_without_exception_details(self):
        runner = Mock(side_effect=FileNotFoundError("/private/path/docker"))
        err = io.StringIO()
        code = ci_docker_build.run_compose(["build"], runner=runner, stderr=err)
        self.assertEqual(code, 127)
        self.assertIn("docker_compose_launch_failed", err.getvalue())
        self.assertNotIn("/private/path", err.getvalue())


if __name__ == "__main__":
    unittest.main()
