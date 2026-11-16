"""Deterministic offline synthetic correlation tests; no runtime access."""
import unittest
from scripts.aiops2_correlation_boundary_20261116 import correlate

NOW = '2026-11-16T05:00:00Z'


def event(**overrides):
    value = dict(tenant_id='demo-a', source='checkmk', source_instance='cmk-1',
                 event_id='e-1', ci_id='san-1', observed_at=NOW)
    value.update(overrides)
    return value


class SyntheticCorrelationBoundaryTests(unittest.TestCase):
    def test_group_same_ci_same_tenant_only(self):
        result = correlate([event(), event(source='prometheus', event_id='p-1'),
                            event(tenant_id='demo-b')], now=NOW)
        self.assertEqual([len(g['signals']) for g in result['correlation']], [2, 1])
        self.assertTrue(all(g['causality'] == 'UNKNOWN' and g['impact'] == 'UNKNOWN'
                            for g in result['correlation']))

    def test_exact_duplicate_collapses(self):
        self.assertEqual(len(correlate([event(), event()], now=NOW)['correlation'][0]['signals']), 1)

    def test_conflicting_duplicate_unknown(self):
        result = correlate([event(), event(ci_id='storage-1')], now=NOW)
        self.assertEqual(result['unknown'][0]['reason'], 'CONTRADICTORY_DUPLICATE')

    def test_future_and_stale_unknown(self):
        result = correlate([event(observed_at='2026-11-16T05:00:01Z'),
                            event(event_id='e-2', observed_at='2026-11-16T04:54:59Z')], now=NOW)
        self.assertEqual(len(result['unknown']), 2)

    def test_boundary_inclusive(self):
        self.assertEqual(len(correlate([event(observed_at='2026-11-16T04:55:00Z')],
                                       now=NOW)['correlation']), 1)

    def test_non_utc_unknown(self):
        result = correlate([event(observed_at='2026-11-16T06:00:00+01:00')], now=NOW)
        self.assertEqual(result['unknown'][0]['reason'], 'INVALID_TIME')

    def test_live_denied(self):
        with self.assertRaises(ValueError):
            correlate([], now=NOW, mode='LIVE')

    def test_bad_freshness_denied(self):
        for value in (True, None, -1, float('nan'), float('inf'), '300'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                correlate([], now=NOW, max_age_seconds=value)

    def test_missing_identity_unknown(self):
        self.assertEqual(correlate([event(tenant_id='')], now=NOW)['unknown'][0]['reason'],
                         'MISSING_IDENTITY')

    def test_source_unknown(self):
        self.assertEqual(correlate([event(source='other')], now=NOW)['unknown'][0]['reason'],
                         'UNKNOWN_SOURCE')


if __name__ == '__main__':
    unittest.main()
