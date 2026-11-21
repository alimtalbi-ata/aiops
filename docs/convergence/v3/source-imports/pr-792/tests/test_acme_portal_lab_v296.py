import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"app/portal/qualification_lab.py"
spec=importlib.util.spec_from_file_location("lab",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LabTests(unittest.TestCase):
    def test_modes_and_noise(self):
        self.assertEqual([len(m.preview(mode,42)) for mode in m.MODES],[4,7,10,24])
    def test_acme_only(self):
        for mode in m.MODES:
            self.assertTrue(all(x["scope"]=="ACME" and x["synthetic"] and x["ci_id"].startswith("ACME-") for x in m.preview(mode,42)))
    def test_reproducibility(self):
        self.assertEqual(m.preview("smoke_screen",7),m.preview("smoke_screen",7))
    def test_reject_bad_mode(self):
        with self.assertRaises(ValueError):m.preview("live",1)
if __name__=="__main__":unittest.main()
