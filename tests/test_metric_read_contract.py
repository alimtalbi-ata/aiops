import unittest
from datetime import datetime, timezone
from app.portal.metric_read_contract import metric_read_model

NOW = datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc)
BASE = dict(actor="operator", tenant="t1", authorized_tenants={"t1"},
            metric="node_memory_used", value=42, observed_at="2026-11-12T13:59:00Z",
            now=NOW, source="prometheus:v30", mode="LIVE", window_seconds=60,
            generation=4, expected_generation=4)


class MetricReadContractTests(unittest.TestCase):
    def check(self, expected, **changes):
        args = {**BASE, **changes}
        result = metric_read_model(**args)
        self.assertEqual(result["state"], expected)
        if expected != "READY":
            self.assertIsNone(result["data"])
        return result

    def test_ready_with_unit_and_provenance(self):
        data = self.check("READY")["data"]
        self.assertEqual(data["unit"], "bytes")
        self.assertEqual(data["source"], "prometheus:v30")

    def test_unauthenticated(self):
        self.assertEqual(self.check("BLOCKED", actor="")["http_status"], 401)

    def test_malformed_server_identity_fails_closed(self):
        for actor, tenant in (("   ", "t1"), (True, "t1"), ([], "t1"),
                              ("operator", "  "), ("operator", None),
                              ("operator", True)):
            with self.subTest(actor=actor, tenant=tenant):
                result = self.check("BLOCKED", actor=actor, tenant=tenant)
                self.assertEqual(result["http_status"], 401)

    def test_invalid_clock_is_unknown_not_exception(self):
        for now in (None, "2026-11-12T14:00:00Z", 42):
            with self.subTest(now=now):
                result = self.check("UNKNOWN", now=now)
                self.assertEqual(result["reason"], "INVALID_TIMESTAMP")

    def test_acl_checked_before_malformed_sample(self):
        result = self.check("BLOCKED", tenant="other", value=object(), now=None)
        self.assertEqual(result["http_status"], 403)

    def test_cross_tenant(self):
        self.assertEqual(self.check("BLOCKED", tenant="t2")["http_status"], 403)

    def test_unapproved_metric(self):
        self.check("BLOCKED", metric="up{job='anything'}")

    def test_unhashable_scope_is_blocked_not_exception(self):
        for field in ("metric", "mode"):
            for malformed in ([], {}, set()):
                with self.subTest(field=field, malformed=type(malformed).__name__):
                    result = self.check("BLOCKED", **{field: malformed})
                    self.assertEqual(result["http_status"], 400)
                    self.assertEqual(result["reason"], "INVALID_SCOPE")

    def test_stale_generation(self):
        self.check("UNKNOWN", generation=3)

    def test_stale_sample(self):
        self.check("UNKNOWN", observed_at="2026-11-12T13:00:00Z")

    def test_future_sample(self):
        self.check("UNKNOWN", observed_at="2026-11-12T14:01:00Z")

    def test_invalid_values(self):
        for value in (float("nan"), float("inf"), True, None):
            with self.subTest(value=value):
                self.check("UNKNOWN", value=value)

    def test_live_replay_mismatch(self):
        self.check("UNKNOWN", source="prometheus:replay")

    def test_no_arbitrary_source(self):
        self.check("UNKNOWN", source="http://localhost:9090")

    def test_bad_window(self):
        self.check("BLOCKED", window_seconds=-1)

    def test_replay_cannot_launder_live_source(self):
        self.check("UNKNOWN", mode="REPLAY", source="prometheus:v30")

    def test_demo_not_attested_by_live_prometheus(self):
        self.check("UNKNOWN", mode="DEMO", source="prometheus:v30")

    def test_replay_source_qualified_only_in_replay(self):
        self.assertEqual(self.check("READY", mode="REPLAY", source="prometheus:replay")["data"]["mode"], "REPLAY")

    def test_missing_acl_collection_fails_closed(self):
        self.assertEqual(self.check("BLOCKED", authorized_tenants=None)["http_status"], 403)

    def test_boolean_generation_fails_closed(self):
        self.check("UNKNOWN", generation=True, expected_generation=1)

    def test_cpu_utilization_outside_ratio_bounds_unknown(self):
        for value in (-0.01, 1.01):
            with self.subTest(value=value):
                result = self.check("UNKNOWN", metric="node_cpu_utilization", value=value)
                self.assertEqual(result["reason"], "OUT_OF_RANGE_SAMPLE")

    def test_negative_resource_and_request_samples_unknown(self):
        for metric in ("node_memory_used", "node_filesystem_available", "http_requests_rate"):
            with self.subTest(metric=metric):
                result = self.check("UNKNOWN", metric=metric, value=-1)
                self.assertEqual(result["reason"], "OUT_OF_RANGE_SAMPLE")

    def test_boundary_samples_remain_ready(self):
        self.check("READY", metric="node_cpu_utilization", value=0)
        self.check("READY", metric="node_cpu_utilization", value=1)
        self.check("READY", metric="node_filesystem_available", value=0)

    def test_bad_mode(self):
        self.check("BLOCKED", mode="LIVE_WRITE")


if __name__ == "__main__":
    unittest.main()
