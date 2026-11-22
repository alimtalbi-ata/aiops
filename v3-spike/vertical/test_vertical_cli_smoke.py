"""Black-box synthetic CLI smoke: no host actions or production authorization."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("vertical_demo.py")

class VerticalCliSmoke(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args],
                              capture_output=True, text=True, timeout=10, check=False)

    def test_default_denies(self):
        proc = self.invoke()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["policy"]["decision"], "DENY")
        self.assertEqual(out["run"]["status"], "blocked")
        self.assertIs(out["production_authorized"], False)

    def test_explicit_approval_is_simulation_only(self):
        proc = self.invoke("--approved-synthetic")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["policy"]["decision"], "SIMULATE_ONLY")
        self.assertIs(out["run"]["executed_on_host"], False)
        self.assertIs(out["production_authorized"], False)
        self.assertEqual(out["gamma"]["receipt"], out["receipt"])

    def test_custom_event_tenant_is_scoped(self):
        event = {"id":"e1","source":"fixture","severity":"warning","resource":"r1","tenant":"tenant-b"}
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "event.json"
            path.write_text(json.dumps(event), encoding="utf-8")
            proc = self.invoke("--event-file", str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["tenant"], "tenant-b")
        self.assertEqual(out["event"], event)
        self.assertIs(out["production_authorized"], False)

    def test_malformed_input_fails_without_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "event.json"
            path.write_text("{not json", encoding="utf-8")
            proc = self.invoke("--event-file", str(path))
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

if __name__ == "__main__":
    unittest.main()
