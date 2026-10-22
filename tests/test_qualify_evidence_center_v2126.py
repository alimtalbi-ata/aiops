import tempfile,unittest
from pathlib import Path
from tools.qualify_evidence_center_v2126 import qualify
class QualificationTests(unittest.TestCase):
    def test_reject_missing_sources(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            with self.assertRaises(ValueError):qualify(p/'none.json',p/'none2.json',p/'none3.json',p,p/'out')
    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);real=p/'real';real.write_text('{}')
            alias=p/'alias';alias.symlink_to(real)
            with self.assertRaises(ValueError):qualify(alias,real,real,p,p/'out')
    def test_reject_nonempty_output(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);out=p/'out';out.mkdir();(out/'marker').touch()
            with self.assertRaises(ValueError):qualify(p/'x',p/'y',p/'z',p,out)
if __name__=='__main__':unittest.main()
