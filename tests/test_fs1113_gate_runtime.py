"""Executable FS1113 production identity fence tests; no Docker or live writes.

Run: python -m unittest discover -s tests -p test_fs1113_gate_runtime.py -v
The gate is copied into a temporary directory and its build/browser invocations
are replaced by no-ops. All docker inspect calls are handled by a fake executable.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

GATE = Path(__file__).resolve().parents[1] / "scripts/fs/FS.1113-history-race-candidate-validation.sh"
EXPECTED = "aiops2-portal:fs1073-csp-candidate"


class GateRuntimeFence(unittest.TestCase):
    def run_gate(self, *, change_id=False, change_image=False, fail_post=False, fail_pre=False, wrong_tag=False):
        source = GATE.read_text(encoding="utf-8")
        # Do not invoke either candidate build or browser gate in this unit test.
        source = source.replace(
            'ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"',
            'ROOT="/nonexistent-fs1113-unit-test"',
        )
        for name in (
            "FS.1097-build-history-chart-candidate.sh",
            "FS.1107-full-history-candidate-external-first-browser.sh",
        ):
            original = 'bash "$ROOT/scripts/fs/' + name + '"'
            self.assertIn(original, source)
            source = source.replace(original, ': # isolated unit-test no-op')
        with tempfile.TemporaryDirectory(prefix="fs1113-gate-") as temp:
            root = Path(temp)
            gate = root / "gate.sh"
            gate.write_text(source, encoding="utf-8")
            docker = root / "docker"
            docker.write_text(
                "#!/usr/bin/env python3\n"
                "import os,sys,pathlib\n"
                "assert sys.argv[1:3] == ['inspect','aiops2-rebuild-portal']\n"
                "counter=pathlib.Path(os.environ['FS1113_COUNTER'])\n"
                "n=int(counter.read_text()) if counter.exists() else 0\n"
                "counter.write_text(str(n+1))\n"
                "post=n>=3\n"
                "if not post and os.environ.get('FS1113_FAIL_PRE')=='1': sys.exit(1)\n"
                "if post and os.environ.get('FS1113_FAIL_POST')=='1': sys.exit(1)\n"
                "fmt=sys.argv[-1]\n"
                "if fmt=='{{.Config.Image}}': value='aiops2-portal:unexpected' if not post and os.environ.get('FS1113_WRONG_TAG')=='1' else 'aiops2-portal:fs1073-csp-candidate'\n"
                "elif fmt=='{{.Id}}': value='container-changed' if post and os.environ.get('FS1113_CHANGE_ID')=='1' else 'container-original'\n"
                "elif fmt=='{{.Image}}': value='sha256:changed' if post and os.environ.get('FS1113_CHANGE_IMAGE')=='1' else 'sha256:original'\n"
                "else: sys.exit(2)\n"
                "print(value)\n",
                encoding="utf-8",
            )
            docker.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "PATH": str(root) + os.pathsep + env.get("PATH", ""),
                "FS1113_COUNTER": str(root / "counter"),
                "FS1113_CHANGE_ID": str(int(change_id)),
                "FS1113_CHANGE_IMAGE": str(int(change_image)),
                "FS1113_FAIL_POST": str(int(fail_post)),
                "FS1113_FAIL_PRE": str(int(fail_pre)),
                "FS1113_WRONG_TAG": str(int(wrong_tag)),
            })
            return subprocess.run(["bash", str(gate)], capture_output=True, text=True, env=env, timeout=10)

    def test_unchanged_production_allows_gate(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("FS1113_RESULT=PASS", result.stdout)

    def test_container_replacement_with_same_tag_fails_closed(self):
        result = self.run_gate(change_id=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("FS1113_ERROR=PRODUCTION_CONTAINER_OR_IMAGE_ID_CHANGED", result.stdout)
        self.assertNotIn("FS1113_RESULT=PASS", result.stdout)

    def test_image_id_replacement_with_same_tag_fails_closed(self):
        result = self.run_gate(change_image=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertNotIn("FS1113_RESULT=PASS", result.stdout)

    def test_unavailable_postcheck_fails_closed(self):
        result = self.run_gate(fail_post=True)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("FS1113_ERROR=PRODUCTION_POSTCHECK_UNAVAILABLE", result.stdout)
        self.assertNotIn("FS1113_RESULT=PASS", result.stdout)


    def test_precheck_unavailable_fails_closed(self):
        result = self.run_gate(fail_pre=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FS1113_RESULT=PASS", result.stdout)

    def test_unexpected_production_tag_fails_closed(self):
        result = self.run_gate(wrong_tag=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("FS1113_ERROR=UNEXPECTED_PRODUCTION_IMAGE", result.stdout)
        self.assertNotIn("FS1113_RESULT=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
