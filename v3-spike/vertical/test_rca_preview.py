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
    def test_measured_recovery_comparison(self):
        scope=["NODE-CI-ROOT","NODE-CI-ENT-ASSET-PAR","NODE-CI-ENT-APP-PAY"]
        rows=[dict(synthetic=True,metric="latency_ms",phase=p,value=v,evidence_id=e,measurement_scope=scope,occurred_at=t)
              for p,v,e,t in (("baseline",10,"E1","2026-01-01T09:00:00Z"),("incident",120,"E2","2026-01-01T09:00:01Z"),("recovery",11,"E3","2026-01-01T09:00:02Z"))]
        d=preview(rows)
        self.assertTrue(d["recovery"]["within_baseline_tolerance"])
        self.assertEqual(d["recovery"]["observed_reduction_ms"],109)
        self.assertFalse(d["recovery"]["causality_established"])
        self.assertEqual(d["evidence_ids"],["E1","E2","E3"])
        self.assertFalse(preview([*rows[:2],dict(rows[2],value=110)])["recovery"]["within_baseline_tolerance"])
        for bad in (dict(rows[2],evidence_id="E2"),dict(rows[2],measurement_scope=None),dict(rows[2],occurred_at="2025-01-01T00:00:00Z")):
            with self.assertRaises(ValueError):preview([*rows[:2],bad])
        with self.assertRaises(ValueError):preview(rows[1:])
