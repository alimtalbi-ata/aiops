import unittest
from datetime import datetime, timezone
from app.portal.metric_read_contract import metric_read_model

NOW = datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc)
BASE = dict(actor="operator", tenant="t1", authorized_tenants={"t1"},
            metric="node_memory_used", value=42, observed_at="2026-11-12T13:59:00Z",
            now=NOW, source="prometheus:v30", mode="LIVE", window_seconds=0,
            generation=4, expected_generation=4, source_attested=True)


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

    def test_huge_integer_sample_is_unknown_not_server_error(self):
        result = self.check("UNKNOWN", value=10 ** 1000)
        self.assertEqual(result["reason"], "INVALID_SAMPLE")
        self.assertEqual(result["http_status"], 200)

    def test_acl_precedes_huge_integer_validation(self):
        result = self.check("BLOCKED", tenant="other", value=10 ** 1000)
        self.assertEqual(result["http_status"], 403)

    def test_live_replay_mismatch(self):
        self.check("UNKNOWN", source="prometheus:replay")

    def test_source_label_alone_cannot_attest_sample(self):
        for attested in (False, None, "true", 1):
            with self.subTest(attested=attested):
                result = self.check("UNKNOWN", source_attested=attested)
                self.assertEqual(result["reason"], "SOURCE_UNATTESTED")

    def test_acl_precedes_source_attestation(self):
        result = self.check("BLOCKED", tenant="other", source_attested=False)
        self.assertEqual(result["http_status"], 403)

    def test_no_arbitrary_source(self):
        self.check("UNKNOWN", source="http://localhost:9090")

    def test_bad_window(self):
        for window in (-1, 1, 60, True, None):
            with self.subTest(window=window):
                result = self.check("BLOCKED", window_seconds=window)
                self.assertEqual(result["reason"], "INVALID_WINDOW")

    def test_promql_window_cannot_be_misreported(self):
        for metric, actual in (("node_cpu_utilization", 300), ("http_requests_rate", 120),
                               ("node_memory_used", 0), ("node_filesystem_available", 0)):
            with self.subTest(metric=metric):
                self.assertEqual(self.check("READY", metric=metric, window_seconds=actual)["data"]["window_seconds"], actual)
                for forged in (60, 120 if actual != 120 else 300, 3600):
                    if forged != actual:
                        self.assertEqual(self.check("BLOCKED", metric=metric, window_seconds=forged)["reason"], "INVALID_WINDOW")

    def test_acl_precedes_window_validation(self):
        self.assertEqual(self.check("BLOCKED", tenant="other", window_seconds=999)["http_status"], 403)

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
        self.check("READY", metric="node_cpu_utilization", value=0, window_seconds=300)
        self.check("READY", metric="node_cpu_utilization", value=1, window_seconds=300)
        self.check("READY", metric="node_filesystem_available", value=0)

    def test_cancelled_read_never_returns_sample(self):
        result = self.check("UNKNOWN", cancelled=True)
        self.assertEqual(result["reason"], "CANCELLED")

    def test_timed_out_read_never_returns_sample(self):
        result = self.check("UNKNOWN", timed_out=True)
        self.assertEqual(result["reason"], "UPSTREAM_TIMEOUT")

    def test_acl_precedes_cancellation_and_timeout(self):
        for flag in ("cancelled", "timed_out"):
            with self.subTest(flag=flag):
                result = self.check("BLOCKED", tenant="other", **{flag: True})
                self.assertEqual(result["http_status"], 403)

    def test_malformed_request_state_is_blocked(self):
        for flag in ("cancelled", "timed_out"):
            for invalid in (None, 1, "false", []):
                with self.subTest(flag=flag, invalid=invalid):
                    result = self.check("BLOCKED", **{flag: invalid})
                    self.assertEqual(result["reason"], "INVALID_REQUEST_STATE")

    def test_bad_mode(self):
        self.check("BLOCKED", mode="LIVE_WRITE")


    def test_freshness_boundary_is_inclusive_and_exceeded_is_unknown(self):
        for metric, window, boundary in (
            ("node_cpu_utilization", 300, "2026-11-12T13:55:00Z"),
            ("node_memory_used", 0, "2026-11-12T13:55:00Z"),
            ("http_requests_rate", 120, "2026-11-12T13:58:00Z"),
        ):
            with self.subTest(metric=metric):
                ready = self.check("READY", metric=metric, window_seconds=window,
                                   observed_at=boundary)
                self.assertEqual(ready["data"]["freshness_seconds"],
                                 120.0 if metric == "http_requests_rate" else 300.0)
                stale = self.check("UNKNOWN", metric=metric, window_seconds=window,
                                   observed_at="2026-11-12T13:54:59Z"
                                   if metric != "http_requests_rate"
                                   else "2026-11-12T13:57:59Z")
                self.assertEqual(stale["reason"], "STALE_SAMPLE")
                self.assertEqual(stale["http_status"], 200)

    def test_acl_precedes_stale_and_future_timestamps(self):
        for observed_at in ("2026-11-12T13:00:00Z", "2026-11-12T14:00:01Z", "bad"):
            with self.subTest(observed_at=observed_at):
                result = self.check("BLOCKED", tenant="other", observed_at=observed_at)
                self.assertEqual(result["http_status"], 403)
                self.assertEqual(result["reason"], "TENANT_DENIED")


if __name__ == "__main__":
    unittest.main()
