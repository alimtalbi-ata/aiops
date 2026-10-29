import importlib.util,json,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"tools/benchmark_acme_reasoning_v296.py"
spec=importlib.util.spec_from_file_location("bench",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class BurnInTests(unittest.TestCase):
    def test_missing_predictions_never_score_as_model_success(self):
        with tempfile.TemporaryDirectory() as d:
            report=m.benchmark(Path(d),seeds=2)
            s=report["summary"]
            self.assertEqual(s["cases_total"],8)
            self.assertEqual(s["cases_missing"],8)
            self.assertEqual(s["cases_evaluated"],0)
            self.assertIsNone(s["mean_f1"])
            self.assertFalse(s["model_inference_performed"])
    def test_tampered_prediction_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"ACME-EXERCISE-SIMPLE-20261021.json"
            path.write_text(json.dumps({"exercise_id":"ACME-EXERCISE-SIMPLE-20261021",
                "observation_sha256":"fake","root_causes":[]}))
            report=m.benchmark(Path(d),seeds=1,modes=["simple"])
            self.assertEqual(report["summary"]["cases_rejected"],1)
            self.assertIsNone(report["summary"]["mean_f1"])
    def test_reject_invalid_repetition_count(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):m.benchmark(Path(d),seeds=0)
if __name__=="__main__":unittest.main()
