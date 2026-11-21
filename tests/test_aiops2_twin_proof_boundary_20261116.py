import unittest
from scripts.aiops2_twin_proof_boundary_20261116 import project

NODES = [{'id': 'san-demo', 'kind': 'SAN', 'tenant': 'demo'}, {'id': 'storage-demo', 'kind': 'STORAGE', 'tenant': 'demo'}, {'id': 'payments-demo', 'kind': 'SERVICE', 'tenant': 'demo'}]
EDGE = {'source': 'san-demo', 'target': 'storage-demo', 'tenant': 'demo', 'authority': 'CMDB', 'evidence_id': 'fixture-1', 'observed_at': '2026-11-16T00:00:00Z', 'attested': True}
NOW = '2026-11-16T00:05:00Z'

class TwinProofBoundaryTests(unittest.TestCase):
    def test_missing_second_edge_unknown(self):
        result = project(NODES, [EDGE], tenant='demo', now=NOW)
        self.assertEqual([x['status'] for x in result['edges']], ['SOURCED_SYNTHETIC', 'UNKNOWN'])
        self.assertFalse(result['live_attested'])
    def test_stale_unknown(self):
        edge = dict(EDGE, observed_at='2026-11-15T00:00:00Z')
        self.assertEqual(project(NODES, [edge], tenant='demo', now=NOW)['edges'][0]['status'], 'UNKNOWN')
    def test_unattested_unknown(self):
        self.assertEqual(project(NODES, [dict(EDGE, attested=False)], tenant='demo', now=NOW)['edges'][0]['status'], 'UNKNOWN')
    def test_cross_tenant_rejected(self):
        with self.assertRaises(ValueError):
            project(NODES, [dict(EDGE, tenant='other')], tenant='demo', now=NOW)
    def test_ambiguous_unknown(self):
        self.assertEqual(project(NODES, [EDGE, EDGE], tenant='demo', now=NOW)['edges'][0]['status'], 'UNKNOWN')
    def test_bool_freshness_rejected(self):
        with self.assertRaises(ValueError):
            project(NODES, [EDGE], tenant='demo', now=NOW, max_age_seconds=True)
    def test_future_unknown(self):
        self.assertEqual(project(NODES, [dict(EDGE, observed_at='2026-11-16T00:06:00Z')], tenant='demo', now=NOW)['edges'][0]['status'], 'UNKNOWN')

if __name__ == '__main__':
    unittest.main()
