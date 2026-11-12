"""F-027: standalone negative release gate, synthetic data only. No network/host access."""
import datetime as dt
import unittest
import re

EXPECTED_SOCKET = "/run/user/1001/docker.sock"
MAX_AGE = dt.timedelta(hours=2)

def gate(report, ci_sha, candidate_sha, now, ci_conclusion=None):
    if not isinstance(ci_sha, str) or not re.fullmatch(r'[0-9a-f]{40}', ci_sha) or ci_sha != candidate_sha:
        return "NO_GO:SHA_MISMATCH"
    if ci_conclusion != "success":
        return "NO_GO:CI_UNVERIFIED"
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        return "NO_GO:TIME_UNKNOWN"
    if not isinstance(report, dict):
        return "NO_GO:HOST_UNKNOWN"
    if report.get("uid") != 1001 or report.get("socket") != EXPECTED_SOCKET or report.get("context") != "rootless":
        return "NO_GO:ROOTLESS_UNVERIFIED"
    try:
        stamp = dt.datetime.fromisoformat(report["collected_at"])
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return "NO_GO:TIME_UNKNOWN"
        age = now - stamp
        if age < dt.timedelta(0) or age > MAX_AGE:
            return "NO_GO:HOST_STALE"
    except (ValueError, TypeError, KeyError):
        return "NO_GO:TIME_UNKNOWN"
    if report.get("complete") is not True:
        return "NO_GO:INVENTORY_UNVERIFIED"
    for kind in ("images", "containers"):
        listing = report.get(kind)
        count = report.get(kind + "_count")
        if not isinstance(listing, list) or type(count) is not int or count < 0:
            return "NO_GO:COUNT_UNKNOWN"
        if count != len(listing):
            return "NO_GO:INVENTORY_INCOMPLETE"
    if report.get("errors") or report.get("timed_out") or report.get("truncated"):
        return "NO_GO:HOST_UNKNOWN"
    return "HOST_EVIDENCE_ELIGIBLE_NOT_DEPLOY_APPROVAL"

class NegativeReleaseGate(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 12, 6, 0, tzinfo=dt.timezone.utc)
        self.r = dict(uid=1001, socket=EXPECTED_SOCKET, context="rootless",
                      collected_at="2026-11-12T05:30:00+00:00",
                      images=["a", "b"], images_count=2,
                      containers=["c"], containers_count=1, complete=True)
    def check(self, expected, **changes):
        self.assertEqual(gate({**self.r, **changes}, "a"*40, "a"*40, self.now, "success"), expected)
    def test_fresh_inventory_is_not_deployment_approval(self):
        self.check("HOST_EVIDENCE_ELIGIBLE_NOT_DEPLOY_APPROVAL")
    def test_stale(self):
        self.check("NO_GO:HOST_STALE", collected_at="2026-11-08T06:00:00+00:00")
    def test_future(self):
        self.check("NO_GO:HOST_STALE", collected_at="2026-11-13T06:00:00+00:00")
    def test_naive_time(self):
        self.check("NO_GO:TIME_UNKNOWN", collected_at="2026-11-12T05:30:00")
    def test_rootful(self):
        self.check("NO_GO:ROOTLESS_UNVERIFIED", context="default")
    def test_count_truncated(self):
        self.check("NO_GO:INVENTORY_INCOMPLETE", images_count=210)
    def test_count_boolean(self):
        self.check("NO_GO:COUNT_UNKNOWN", images_count=True)
    def test_timeout(self):
        self.check("NO_GO:HOST_UNKNOWN", timed_out=True)
    def test_ci_missing_or_failed(self):
        self.assertEqual(gate(self.r, "a"*40, "a"*40, self.now), "NO_GO:CI_UNVERIFIED")
        self.assertEqual(gate(self.r, "a"*40, "a"*40, self.now, "failure"), "NO_GO:CI_UNVERIFIED")
    def test_complete_missing_or_false(self):
        self.check("NO_GO:INVENTORY_UNVERIFIED", complete=False)
        self.check("NO_GO:INVENTORY_UNVERIFIED", complete=None)
    def test_naive_now(self):
        self.assertEqual(gate(self.r, "a"*40, "a"*40, self.now.replace(tzinfo=None), "success"), "NO_GO:TIME_UNKNOWN")
    def test_non_sha_identifier(self):
        self.assertEqual(gate(self.r, "candidate", "candidate", self.now, "success"), "NO_GO:SHA_MISMATCH")
    def test_sha_mismatch(self):
        self.assertEqual(gate(self.r, "a"*40, "b"*40, self.now, "success"), "NO_GO:SHA_MISMATCH")

if __name__ == "__main__":
    unittest.main()
