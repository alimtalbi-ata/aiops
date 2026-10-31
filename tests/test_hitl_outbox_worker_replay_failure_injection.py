"""Offline outbox notification fault injection: no network, DB or Temporal service.

The Core decision is authoritative; these tests never model a real human identity,
approval authorization, executor, or any effect. Restart is a fresh coroutine.
"""
import ast
import asyncio
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class EndScan(Exception):
    pass


class OfflineClient:
    def __init__(self, signals):
        self.signals = signals
        self.connects = 0

    async def connect(self, address):
        self.connects += 1
        return self

    def get_workflow_handle(self, run_id):
        if run_id != "RUN-ISOLATED":
            raise AssertionError("unexpected_run")
        return self

    async def signal(self, signal_method, payload):
        self.signals.append(dict(payload))


def event(**changes):
    item = {"event_id": "HDO-ISOLATED", "run_id": "RUN-ISOLATED",
            "proposal_id": "ACT-ISOLATED", "proposal_hash": "hash-isolated",
            "proposal_revision": 1, "decision": "REJECT",
            "source_status": "REJECTED", "lease_token": "lease-1"}
    item.update(changes)
    return item


def scan_once(claims, *, lost_ack=False, signals=None, acknowledgements=None):
    """Execute one AST-extracted scan; interrupt only the idle sleep."""
    signals = [] if signals is None else signals
    acknowledgements = [] if acknowledgements is None else acknowledgements
    client = OfflineClient(signals)
    requests = []

    def post(base, path, payload, **kwargs):
        requests.append((path, dict(payload)))
        if path.endswith("/claim"):
            return claims
        if path.endswith("/delivered"):
            if lost_ack:
                raise ConnectionError("injected_lost_ack")
            acknowledgements.append(dict(payload))
            return {"execution_allowed": False, "effect_allowed": False}
        raise AssertionError("unexpected_request")

    async def stop_after_scan(seconds):
        raise EndScan()

    source = (ROOT / "app/worker/main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                and n.name == "reconcile_hitl_decisions_loop")
    node.decorator_list = []
    logger = types.SimpleNamespace(debug=lambda *a: None, warning=lambda *a: None)
    env = {"Client": client, "TEMP": "offline", "CORE": "offline",
           "DENIAL_WORKER_OWNER": "offline-worker", "ADMIN": "offline",
           "post_json": post, "log": logger,
           "IncidentWorkflow": types.SimpleNamespace(submit_hitl_decision=object()),
           "asyncio": types.SimpleNamespace(sleep=stop_after_scan)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 "app/worker/main.py", "exec"), env)
    with unittest.TestCase().assertRaises(EndScan):
        asyncio.run(env["reconcile_hitl_decisions_loop"]())
    return signals, acknowledgements, requests


class OutboxWorkerReplayFaultTests(unittest.TestCase):
    def test_corrupted_claim_envelope_never_signals(self):
        for bad in (None, [], {}, {"items": [event()]},
                    {"execution_allowed": True, "effect_allowed": False,
                     "items": [event()]},
                    {"execution_allowed": False, "effect_allowed": True,
                     "items": [event()]},
                    {"execution_allowed": False, "effect_allowed": False,
                     "items": "not-a-list"}):
            with self.subTest(bad=bad):
                signals, acks, requests = scan_once(bad)
                self.assertEqual((signals, acks), ([], []))
                self.assertEqual(len(requests), 1)

    def test_invalid_revision_source_status_and_effect_claim_never_signal(self):
        mutations = (
            {"proposal_revision": 0}, {"proposal_revision": -1},
            {"proposal_revision": True}, {"proposal_revision": 1.0},
            {"source_status": "APPROVED"}, {"source_status": "UNKNOWN"},
            {"source_status": ""}, {"decision": "APPROVE"},
            {"execution_allowed": True}, {"effect_allowed": True},
            {"lease_token": ""}, {"proposal_hash": ""},
        )
        for change in mutations:
            with self.subTest(change=change):
                claim = {"execution_allowed": False, "effect_allowed": False,
                         "items": [event(**change)]}
                signals, acks, requests = scan_once(claim)
                self.assertEqual((signals, acks), ([], []))
                self.assertEqual(len(requests), 1)

    def test_lost_ack_then_worker_restart_replays_same_decision_without_effect(self):
        signals, acknowledgements = [], []
        first = {"execution_allowed": False, "effect_allowed": False,
                 "items": [event()]}
        scan_once(first, lost_ack=True, signals=signals,
                  acknowledgements=acknowledgements)
        self.assertEqual(len(signals), 1)
        self.assertEqual(acknowledgements, [])
        # Model lease expiry/reclaim and a fresh worker coroutine, not real DB time.
        second = {"execution_allowed": False, "effect_allowed": False,
                  "items": [event(lease_token="lease-2")]}
        scan_once(second, signals=signals, acknowledgements=acknowledgements)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0], signals[1])
        self.assertEqual(acknowledgements, [{"lease_token": "lease-2"}])
        self.assertEqual(signals[0]["decision"], "REJECT")
        self.assertNotIn("execution_allowed", signals[0])
        self.assertNotIn("effect_allowed", signals[0])

    def test_valid_revoke_is_notification_only(self):
        claim = {"execution_allowed": False, "effect_allowed": False,
                 "items": [event(source_status="REVOKED")]}
        signals, acks, _ = scan_once(claim)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["decision"], "REJECT")
        self.assertEqual(signals[0]["source_status"], "REVOKED")
        self.assertEqual(acks, [{"lease_token": "lease-1"}])


if __name__ == "__main__":
    unittest.main()
