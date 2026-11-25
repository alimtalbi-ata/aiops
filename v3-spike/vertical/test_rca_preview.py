import unittest
from rca_preview import preview

class PreviewTest(unittest.TestCase):
    def test_counterfactual(self):
        rows=[dict(synthetic=True,metric="latency_ms",phase="baseline",value=40,evidence_id="E1"),
              dict(synthetic=True,metric="latency_ms",phase="incident",value=160,evidence_id="E2")]
        result=preview(rows)
        self.assertEqual(result["hypothesis"],"LATENCY_REGRESSION_OBSERVED")
        self.assertEqual(result["root_cause"],"UNKNOWN")
        self.assertEqual(result["preview"]["conditional_reduction_ms"],120)
        self.assertEqual(result["evidence_ids"],["E1","E2"])
        self.assertFalse(result["executed_on_host"])
        self.assertIsNone(preview(rows[:1])["preview"])
        self.assertIsNone(preview([dict(r,synthetic=False) for r in rows])["preview"])
        with self.assertRaises(ValueError):
            preview([rows[0],dict(rows[1],evidence_id="E1")])
        with self.assertRaises(ValueError):
            preview([rows[0],dict(rows[1],value=float("nan"))])
