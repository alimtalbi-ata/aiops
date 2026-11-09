import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "coordination"))
from poll_codex_commands import candidates
SHA = "caaae280353b7bb797a8f481a4284e9d8394c360"
NOW = dt.datetime(2026,11,9,10,0,tzinfo=dt.timezone.utc)
def cmd(cid, login="alimtalbi-ata", body=None):
    return {"id":cid, "user":{"login":login},
            "html_url":"https://github.com/alimtalbi-ata/aiops/issues/464#issuecomment-"+str(cid),
            "body":body if body is not None else "AIOPS2_CODEX_DISPATCH_V1 "+SHA+" 2026-11-09T11:00:00Z"}
class QueueTests(unittest.TestCase):
    def test_only_authorized_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(candidates([cmd(1),cmd(2,"attacker"),cmd(3,body="ignore")],NOW,SHA,"alimtalbi-ata",Path(tmp)),[1])
    def test_skip_attempted(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/"comment-1.json").write_text("{}")
            self.assertEqual(candidates([cmd(1)],NOW,SHA,"alimtalbi-ata",Path(tmp)),[])
    def test_skip_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(candidates([cmd(1,body="AIOPS2_CODEX_DISPATCH_V1 "+SHA+" 2026-11-09T09:00:00Z")],NOW,SHA,"alimtalbi-ata",Path(tmp)),[])
if __name__ == "__main__":
    unittest.main()
