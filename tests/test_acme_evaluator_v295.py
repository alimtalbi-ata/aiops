import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"tools/evaluate_acme_adversarial_v295.py"
spec=importlib.util.spec_from_file_location("evaluator",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
TRUTH={"exercise_id":"ACME-X","root_causes":[{"root_cause_id":"RC-A"},{"root_cause_id":"RC-B"}],
       "unrelated_observation_count":14}
class EvaluatorTests(unittest.TestCase):
    def test_perfect_prediction(self):
        result=m.evaluate(TRUTH,{"root_causes":[{"root_cause_id":"RC-A"},{"root_cause_id":"RC-B"}]},[])
        self.assertEqual(result["f1"],1)
        self.assertIsNone(result["noise_resistance_score"])
    def test_false_cause_penalized(self):
        result=m.evaluate(TRUTH,{"root_causes":[{"root_cause_id":"RC-A"},{"root_cause_id":"RC-FAKE"}]},[])
        self.assertEqual(result["precision"],.5)
        self.assertEqual(result["recall"],.5)
        self.assertEqual(result["false_positives"],1)
    def test_no_predictions_not_a_success(self):
        result=m.evaluate(TRUTH,{"root_causes":[]},[])
        self.assertEqual(result["f1"],0)
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            m.evaluate(TRUTH,{"root_causes":[{"root_cause_id":"RC-A"},{"root_cause_id":"RC-A"}]},[])
if __name__=="__main__":unittest.main()
