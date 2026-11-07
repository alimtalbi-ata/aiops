"""Fail-closed tests for durable Core idempotency acknowledgement.

Fakes exercise orchestration only; they do not attest a real bridge or Core.
"""
import unittest

from worker.fs147_readonly_pipeline import FS147Request, execute


REQUEST = FS147Request("tenant", "actor", "incident", "run", ticket_id=147)


class ClaimAcknowledgementTests(unittest.TestCase):
    def test_ambiguous_claims_never_call_bridge_or_agents(self):
        for acknowledgement in (None, False, 0, 1, "true", "claimed", [], {}, object()):
            with self.subTest(acknowledgement=repr(acknowledgement)):
                called = []
                def unexpected(*args):
                    called.append(args)
                    raise AssertionError("downstream call after invalid claim")
                result = execute(
                    REQUEST, stop_auto=False, claim_once=lambda _: acknowledgement,
                    observe=unexpected, analyst=unexpected, critic=unexpected,
                    policy=unexpected,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["effect"], "NO_EFFECT")
                self.assertEqual(result["reason"], "DUPLICATE_RUN")
                self.assertFalse(result["resolved"])
                self.assertEqual(called, [])

    def test_claim_failure_does_not_call_bridge(self):
        called = []
        def failed(_):
            raise TimeoutError("Core unavailable")
        def unexpected(*args):
            called.append(args)
            raise AssertionError("unexpected downstream call")
        result = execute(
            REQUEST, stop_auto=False, claim_once=failed,
            observe=unexpected, analyst=unexpected, critic=unexpected,
            policy=unexpected,
        )
        self.assertEqual(result["reason"], "IDEMPOTENCY_UNAVAILABLE")
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertEqual(called, [])

    def test_stop_auto_precedes_durable_claim(self):
        called = []
        def unexpected(*args):
            called.append(args)
            raise AssertionError("unexpected call")
        result = execute(
            REQUEST, stop_auto=True, claim_once=unexpected,
            observe=unexpected, analyst=unexpected, critic=unexpected,
            policy=unexpected,
        )
        self.assertEqual(result["reason"], "STOP_AUTO")
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
