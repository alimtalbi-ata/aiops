"""Unit tests for the disconnected projection policy; no HTTP authorization claim."""
import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("portal_projection", ROOT / "app" / "portal" / "operational_projection.py")
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)
NOW = datetime(2026, 11, 10, 16, 25, tzinfo=timezone.utc)
IDENTITY = {"actor_id": "operator-1", "verified": True}
SOURCE = {"tenant_id": "tenant-A", "scope_verified": True, "records": [{"id": "run-1"}], "observed_at": "2026-11-10T16:24:00Z"}


def project(**overrides):
    params = dict(identity=IDENTITY, tenant_id="tenant-A", authorized_tenants={"tenant-A"}, source=SOURCE, now=NOW)
    params.update(overrides)
    return projection.project_authorized_records(**params)


class ProjectionPolicyTests(unittest.TestCase):
    def test_authorized_fresh_records(self):
        result = project()
        self.assertEqual(result["authorization_source"], "server")
        self.assertEqual(result["records"], SOURCE["records"])
        self.assertTrue(result["scope_verified"])

    def test_verified_fresh_empty(self):
        self.assertEqual(project(source={**SOURCE, "records": []})["records"], [])

    def test_identity_and_membership_fail_closed(self):
        for identity in (None, {}, {"actor_id": "operator-1"}, {"actor_id": "", "verified": True}):
            with self.subTest(identity=identity), self.assertRaises(projection.ProjectionDenied):
                project(identity=identity)
        for tenants in (set(), {"tenant-B"}, ["tenant-A"]):
            with self.subTest(tenants=tenants), self.assertRaises(projection.ProjectionDenied):
                project(authorized_tenants=tenants)

    def test_unverified_or_mismatched_source_fails_closed(self):
        for source in (None, {}, {**SOURCE, "scope_verified": False}, {**SOURCE, "tenant_id": "tenant-B"}, {**SOURCE, "records": None}):
            with self.subTest(source=source), self.assertRaises(projection.ProjectionUnavailable):
                project(source=source)

    def test_mixed_tenant_records_denied_even_with_source_attestation(self):
        for records in ([{"tenant_id": "tenant-B", "id": "foreign"}], [{"tenant_id": "tenant-A"}, {"tenant_id": "tenant-B"}], ["not-a-record"]):
            with self.subTest(records=records), self.assertRaises(projection.ProjectionUnavailable):
                project(source={**SOURCE, "records": records})

    def test_projection_is_snapshot_not_source_alias(self):
        source = {**SOURCE, "records": [{"id": "run-1", "details": {"state": "READY"}}]}
        result = project(source=source)
        source["records"][0]["details"]["state"] = "MUTATED"
        self.assertEqual(result["records"][0]["details"]["state"], "READY")

    def test_timestamp_fails_closed(self):
        for timestamp in (None, "", "not-a-date", "2026-11-10T16:24:00", "2026-11-10T16:20:00Z", "2026-11-10T16:26:00Z"):
            with self.subTest(timestamp=timestamp), self.assertRaises(projection.ProjectionUnavailable):
                project(source={**SOURCE, "observed_at": timestamp})

    def test_bad_freshness_policy_fails_closed(self):
        for budget in (0, -1, 3601, None, True, float('nan'), float('inf'), float('-inf')):
            with self.subTest(budget=budget), self.assertRaises(projection.ProjectionUnavailable):
                project(max_age_seconds=budget)


if __name__ == "__main__":
    unittest.main()
