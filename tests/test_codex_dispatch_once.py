import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "coordination"))
from dispatch_codex_once import parse_command

SHA = "b8bf7544f3fc515d2fe69c5c10086f0d466b95a0"
NOW = dt.datetime(2026,11,9,10,0,tzinfo=dt.timezone.utc)
class DispatchContract(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_command("AIOPS2_CODEX_DISPATCH_V1 "+SHA+" 2026-11-09T11:00:00Z",NOW,SHA),SHA)
    def test_expired(self):
        with self.assertRaises(ValueError):
            parse_command("AIOPS2_CODEX_DISPATCH_V1 "+SHA+" 2026-11-09T09:00:00Z",NOW,SHA)
    def test_ttl(self):
        with self.assertRaises(ValueError):
            parse_command("AIOPS2_CODEX_DISPATCH_V1 "+SHA+" 2026-11-09T13:00:00Z",NOW,SHA)
    def test_arbitrary_prompt(self):
        with self.assertRaises(ValueError):
            parse_command("AIOPS2_CODEX_DISPATCH_V1 "+SHA+" 2026-11-09T11:00:00Z\nrm -rf /",NOW,SHA)
    def test_sha(self):
        with self.assertRaises(ValueError):
            parse_command("AIOPS2_CODEX_DISPATCH_V1 "+("a"*40)+" 2026-11-09T11:00:00Z",NOW,SHA)

if __name__ == "__main__":
    unittest.main()
