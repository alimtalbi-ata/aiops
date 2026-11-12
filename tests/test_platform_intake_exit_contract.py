"""Offline regression: the installer must not turn a platform HOLD into success."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "install_platform_readiness.py"
spec = importlib.util.spec_from_file_location("install_platform_readiness", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PlatformIntakeExitContract(unittest.TestCase):
    def test_gate_exit_codes_are_preserved(self):
        payload = b"print('read-only gate fixture')\n"
        sha = hashlib.sha256(payload).hexdigest()
        for gate_code, expected in ((0, 0), (2, 2), (1, 1)):
            with self.subTest(gate_code=gate_code), tempfile.TemporaryDirectory() as home:
                class Response:
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def read(self, size=-1): return payload
                completed = mock.Mock(returncode=gate_code, stdout="gate", stderr="")
                with mock.patch.dict(os.environ, {"HOME": home}), \
                     mock.patch.object(module.Path, "home", return_value=Path(home)), \
                     mock.patch.object(module.urllib.request, "urlopen", return_value=Response()), \
                     mock.patch.object(module.subprocess, "run", return_value=completed), \
                     mock.patch("sys.argv", ["install_platform_readiness.py", "--sha256", sha, "--output-dir", str(Path(home)/"receipts")]), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    result = module.main()
                self.assertEqual(result, expected)
                receipts = list((Path(home)/"receipts").glob("release-intake-*.json"))
                self.assertEqual(len(receipts), 1)
                self.assertEqual(json.loads(receipts[0].read_text())["exit_code"], gate_code)


if __name__ == "__main__":
    unittest.main()
