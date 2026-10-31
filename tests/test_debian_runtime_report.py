import datetime as dt
import tempfile
from pathlib import Path
import unittest

from scripts.check_debian_runtime_report import evaluate_report, load_report


NOW = dt.datetime(2026, 10, 31, 20, 0, tzinfo=dt.timezone.utc)


def fresh_report():
    return {
        "schema_version": 3,
        "collected_at": "2026-10-31T19:55:00+00:00",
        "agent": {"name": "aiops-debian-readonly", "version": "1.1.0"},
        "host": {"reported_name": "SRV-DEB-05"},
        "docker": {
            "available": True,
            "truncated": False,
            "containers": [
                {"name": name, "state": "running", "health": "healthy"}
                for name in (
                    "aiops2-rebuild-core",
                    "aiops2-rebuild-worker",
                    "aiops2-rebuild-policy",
                    "aiops2-rebuild-portal",
                )
            ],
        },
        "tcp_published": [
            {"service": name, "reachable": True}
            for name in ("portal", "glpi", "grafana", "prometheus", "temporal_ui")
        ],
    }


class DebianRuntimeReportTests(unittest.TestCase):
    def test_fresh_schema_three_snapshot_passes(self):
        result = evaluate_report(fresh_report(), now=NOW)
        self.assertTrue(result["snapshot_fresh"])
        self.assertEqual(result["runtime_observation"], "PASS")
        self.assertEqual(result["age_seconds"], 300)
        self.assertEqual(result["warnings"], [])

    def test_stale_snapshot_is_refused(self):
        report = fresh_report()
        report["collected_at"] = "2026-10-31T19:30:00+00:00"
        with self.assertRaisesRegex(ValueError, "report_stale"):
            evaluate_report(report, now=NOW)

    def test_future_snapshot_is_refused(self):
        report = fresh_report()
        report["collected_at"] = "2026-10-31T20:02:00+00:00"
        with self.assertRaisesRegex(ValueError, "future"):
            evaluate_report(report, now=NOW)

    def test_timezone_naive_timestamp_is_refused(self):
        report = fresh_report()
        report["collected_at"] = "2026-10-31T19:55:00"
        with self.assertRaisesRegex(ValueError, "timezone_required"):
            evaluate_report(report, now=NOW)

    def test_wrong_host_agent_or_schema_is_refused(self):
        for field, value, error in (
            ("schema_version", 2, "unsupported_report_schema"),
            ("host", {"reported_name": "OTHER"}, "unexpected_report_host"),
            ("agent", {"name": "other", "version": "1.1.0"}, "unexpected_report_agent"),
        ):
            report = fresh_report()
            report[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, error):
                    evaluate_report(report, now=NOW)

    def test_unreachable_published_service_is_warning_not_false_success(self):
        report = fresh_report()
        report["tcp_published"][0]["reachable"] = False
        result = evaluate_report(report, now=NOW)
        self.assertEqual(result["runtime_observation"], "WARN")
        self.assertIn("published_endpoint_unreachable:portal", result["warnings"])

    def test_missing_or_unavailable_docker_inventory_is_explicit_warning(self):
        report = fresh_report()
        report["docker"] = {"available": False}
        result = evaluate_report(report, now=NOW)
        self.assertEqual(result["runtime_observation"], "WARN")
        self.assertIn("docker_inventory_unavailable", result["warnings"])
        self.assertIn("container_not_observed:aiops2-rebuild-core", result["warnings"])

    def test_unhealthy_required_container_is_warning(self):
        report = fresh_report()
        report["docker"]["containers"][0]["health"] = "unhealthy"
        result = evaluate_report(report, now=NOW)
        self.assertIn("container_unhealthy:aiops2-rebuild-core", result["warnings"])

    def test_missing_required_published_probe_is_unknown_warning(self):
        report = fresh_report()
        report["tcp_published"] = []
        result = evaluate_report(report, now=NOW)
        self.assertIn("published_endpoint_not_observed:portal", result["warnings"])

    def test_report_file_is_bounded_and_regular(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            path.write_text('{"schema_version":3}')
            self.assertEqual(load_report(path)["schema_version"], 3)
            path.write_text(" " * (64 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "size_limit"):
                load_report(path)


if __name__ == "__main__":
    unittest.main()
