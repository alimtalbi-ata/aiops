import unittest
from app.portal.prometheus_query_catalog import resolve_prometheus_query


class PrometheusQueryCatalogTests(unittest.TestCase):
    def query(self, **changes):
        return resolve_prometheus_query(**{
            "metric": "node_cpu_utilization", "mode": "LIVE",
            "server_authorized": True, "datasource_attested": True,
            "tenant_isolated": True, **changes})

    def test_fixed_query(self):
        self.assertEqual(
            self.query(),
            '1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))')

    def test_arbitrary_promql_and_unhashable_inputs_rejected(self):
        for metric in ('up{job="other"}', '__name__', {}, [], None, 1):
            with self.subTest(metric=metric):
                self.assertIsNone(self.query(metric=metric))

    def test_no_unqualified_live_access(self):
        for flag in ("server_authorized", "datasource_attested", "tenant_isolated"):
            for invalid in (False, None, 1, "true"):
                with self.subTest(flag=flag, invalid=invalid):
                    self.assertIsNone(self.query(**{flag: invalid}))

    def test_demo_and_replay_not_live_prometheus(self):
        for mode in ("DEMO", "REPLAY", None, [], "LIVE;drop"):
            with self.subTest(mode=mode):
                self.assertIsNone(self.query(mode=mode))


if __name__ == "__main__":
    unittest.main()
