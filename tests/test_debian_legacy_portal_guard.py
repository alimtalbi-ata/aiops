"""Static and executable fail-closed guard for legacy standalone portal installer."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "deploy-demo-studio-v2.sh"

class DebianLegacyPortalGuardTests(unittest.TestCase):
    def test_01_bash_syntax_and_guard_precedes_all_mutations(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(INSTALLER)], capture_output=True).returncode, 0)
        src = INSTALLER.read_text()
        guard = src.index("exit 78")
        for mutation in ('docker stop "$OLD"', 'docker rename "$OLD"', 'docker run -d', 'cp "$DELIVERY/'):
            self.assertIn(mutation, src)
            self.assertGreater(src.index(mutation), guard)
        self.assertLess(guard, src.index('SRC="${SRC:-'))

    def test_02_runtime_guard_no_docker_or_file_write(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            marker = d / "called"
            for name in ("docker", "curl", "cp", "git"):
                tool = d / name
                tool.write_text("#!/bin/sh\nprintf called >> '" + str(marker) + "'\nexit 99\n")
                tool.chmod(0o755)
            env = dict(os.environ, PATH=td + os.pathsep + os.environ["PATH"])
            p = subprocess.run(["bash", str(INSTALLER)], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(p.returncode, 78, p.stderr)
            self.assertIn("legacy standalone portal replacement disabled", p.stderr)
            self.assertFalse(marker.exists())

if __name__ == "__main__":
    unittest.main()
