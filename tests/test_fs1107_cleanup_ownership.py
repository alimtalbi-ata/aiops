"""FS1107 candidate cleanup must never delete a pre-existing container.

Run: python -m unittest discover -s tests -p test_fs1107_cleanup_ownership.py -v
No Docker daemon, host port, or production access is used.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/fs/FS.1107-full-history-candidate-external-first-browser.sh"


class CandidateCleanupOwnership(unittest.TestCase):
    def test_preexisting_candidate_is_not_removed(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("CANDIDATE_CREATED=NO")
        end = source.index('echo "FS1107_MODE=', start)
        # Execute only the real cleanup/trap block with a fake docker binary.
        snippet = source[start:end] + '\nNAME=preexisting-candidate\nexit 2\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "docker"
            fake.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FS1107_DOCKER_LOG\"\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            log = root / "docker.log"
            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env.get("PATH", "")
            env["FS1107_DOCKER_LOG"] = str(log)
            result = subprocess.run(["bash", "-c", snippet], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(log.exists(), "cleanup touched Docker despite no candidate ownership")

    def test_owned_candidate_is_removed(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("CANDIDATE_CREATED=NO")
        end = source.index('echo "FS1107_MODE=', start)
        snippet = source[start:end] + '\nNAME=owned-candidate\nCANDIDATE_CREATED=YES\nexit 0\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "docker"
            fake.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FS1107_DOCKER_LOG\"\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            log = root / "docker.log"
            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env.get("PATH", "")
            env["FS1107_DOCKER_LOG"] = str(log)
            result = subprocess.run(["bash", "-c", snippet], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().strip(), "rm -f owned-candidate")


if __name__ == "__main__":
    unittest.main()
