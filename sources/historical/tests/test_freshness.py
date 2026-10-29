import datetime
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
from shared.freshness import assess_evidence_freshness, annotate_evidence_freshness

NOW=datetime.datetime(2026,10,19,12,0,0,tzinfo=datetime.timezone.utc)

class EvidenceFreshnessTests(unittest.TestCase):
    def test_recent_timestamp_is_fresh(self):
        result=assess_evidence_freshness([{"evidence_id":"E1","observed_at":"2026-10-19T11:55:00Z"}],now=NOW,max_age_seconds=900)
        self.assertEqual(result["status"],"FRESH")
        self.assertEqual(result["fresh_count"],1)

    def test_old_timestamp_is_stale(self):
        result=assess_evidence_freshness([{"evidence_id":"E1","observed_at":"2026-10-19T10:00:00Z"}],now=NOW,max_age_seconds=900)
        self.assertEqual(result["status"],"STALE")
        self.assertEqual(result["stale_count"],1)

    def test_missing_or_naive_timestamp_is_unknown(self):
        result=assess_evidence_freshness([{"evidence_id":"E1","observed_at":"2026-10-19T11:59:00"}],now=NOW,max_age_seconds=900)
        self.assertEqual(result["status"],"UNKNOWN")
        self.assertEqual(result["unknown_count"],1)

    def test_future_timestamp_beyond_clock_skew_is_not_fresh(self):
        result=assess_evidence_freshness([{"evidence_id":"E1","observed_at":"2026-10-19T12:10:00Z"}],now=NOW,max_age_seconds=900)
        self.assertEqual(result["status"],"STALE")
        self.assertEqual(result["future_count"],1)

    def test_mixed_fresh_and_stale_evidence_fails_closed(self):
        result=assess_evidence_freshness([
            {"evidence_id":"E1","observed_at":"2026-10-19T11:59:00Z"},
            {"evidence_id":"E2","observed_at":"2026-10-19T10:00:00Z"}
        ],now=NOW,max_age_seconds=900)
        self.assertEqual(result["status"],"STALE")

    def test_annotation_preserves_original_and_adds_deterministic_quality(self):
        source=[{"evidence_id":"E1","observed_at":"2026-10-19T11:59:00Z"}]
        annotated,summary=annotate_evidence_freshness(source,now=NOW,max_age_seconds=900)
        self.assertNotIn("_aiops_quality",source[0])
        self.assertEqual(annotated[0]["_aiops_quality"]["status"],"FRESH")
        self.assertEqual(summary["status"],"FRESH")

if __name__=="__main__":
    unittest.main()
