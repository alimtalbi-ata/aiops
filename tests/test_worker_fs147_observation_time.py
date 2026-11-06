"""Reject unverifiable bridge observation timestamps before calling agents."""
import unittest
from worker.fs147_readonly_pipeline import FS147Request, execute

REQUEST = FS147Request("tenant", "actor", "incident", "run")


def observation(value):
    return dict(tenant_id="tenant", incident_id="incident", run_id="run",
                ticket_id=147, evidence_id="ev", source="fs-lab-bridge-readonly",
                commands=["df", "du", "ls"], read_only=True,
                filesystem="/fs-lab", used_percent=92, collected_at=value)


class ObservationTimeTests(unittest.TestCase):
    def test_malformed_or_naive_timestamp_short_circuits(self):
        for value in ("now", "", "2026-11-06T00:00:00",
                      "2026-11-06T99:00:00", None, 123):
            with self.subTest(value=value):
                calls = []
                def downstream(*args):
                    calls.append("DOWNSTREAM")
                    raise AssertionError("Agent called on invalid observation")
                result = execute(REQUEST, stop_auto=False,
                    claim_once=lambda _: True,
                    observe=lambda _: observation(value),
                    analyst=downstream, critic=downstream, policy=downstream)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["reason"], "INSUFFICIENT_OBSERVATION")
                self.assertFalse(result["resolved"])
                self.assertEqual(result["effect"], "NO_EFFECT")
                self.assertEqual(calls, [])

    def test_explicit_utc_offset_is_accepted(self):
        for value in ("2026-11-06T00:00:00Z", "2026-11-06T01:00:00+01:00"):
            with self.subTest(value=value):
                def scoped(**kwargs):
                    return dict(tenant_id="tenant", incident_id="incident",
                                run_id="run", ticket_id=147, evidence_id="ev", **kwargs)
                result = execute(REQUEST, stop_auto=False,
                    claim_once=lambda _: True,
                    observe=lambda _: observation(value),
                    analyst=lambda *args: scoped(findings=["read-only observation"]),
                    critic=lambda *args: scoped(state="PASS"),
                    policy=lambda *args: scoped(state="PASS", decision="SIMULATE"))
                self.assertEqual(result["status"], "NO_EFFECT")
                self.assertFalse(result["resolved"])


if __name__ == "__main__":
    unittest.main()
