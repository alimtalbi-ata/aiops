"""FS1107 cleanup must only remove the exact candidate container ID.

Run: python -m unittest discover -s tests -p test_fs1107_cleanup_ownership.py -v
All Docker calls use a fake executable; no host mutation.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/fs/FS.1107-full-history-candidate-external-first-browser.sh"


class CandidateCleanupOwnership(unittest.TestCase):
    def run_cleanup(self, *, owned_id="", current_id="owned-123", inspect_fails=False):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index('CANDIDATE_ID=""')
        end = source.index('echo "FS1107_MODE=', start)
        snippet = source[start:end] + (
            '\nNAME=candidate\nCANDIDATE_ID="' + owned_id + '"\nexit 0\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "docker"
            fake.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >> "$FS1107_DOCKER_LOG"\n'
                'if [ "$1" = inspect ]; then\n'
                '  if [ "$FS1107_INSPECT_FAILS" = yes ]; then exit 1; fi\n'
                '  printf "%s\\n" "$FS1107_CURRENT_ID"\n'
                'fi\n',
                encoding="utf-8",
            )
            fake.chmod(0o755)
            log = root / "docker.log"
            env = os.environ.copy()
            env.update({
                "PATH": str(root) + os.pathsep + env.get("PATH", ""),
                "FS1107_DOCKER_LOG": str(log),
                "FS1107_CURRENT_ID": current_id,
                "FS1107_INSPECT_FAILS": "yes" if inspect_fails else "no",
            })
            result = subprocess.run(["bash", "-c", snippet], env=env, capture_output=True, text=True)
            commands = log.read_text().splitlines() if log.exists() else []
            self.assertEqual(result.returncode, 0, result.stderr)
            return commands, result.stderr

    def test_preexisting_candidate_is_not_removed(self):
        commands, _ = self.run_cleanup()
        self.assertEqual(commands, [])

    def test_owned_candidate_is_removed_by_id(self):
        commands, _ = self.run_cleanup(owned_id="owned-123")
        self.assertEqual(commands, ["inspect candidate --format {{.Id}}", "rm -f owned-123"])

    def test_replaced_candidate_is_never_removed(self):
        commands, stderr = self.run_cleanup(owned_id="owned-123", current_id="replacement-456")
        self.assertEqual(commands, ["inspect candidate --format {{.Id}}"])
        self.assertIn("FS1107_CLEANUP_SKIPPED=IDENTITY_CHANGED", stderr)

    def test_unavailable_identity_does_not_remove_candidate(self):
        commands, _ = self.run_cleanup(owned_id="owned-123", inspect_fails=True)
        self.assertEqual(commands, ["inspect candidate --format {{.Id}}"])


if __name__ == "__main__":
    unittest.main()
