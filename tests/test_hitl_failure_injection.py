"""Isolated #194 failure injection. No network, database or Temporal service."""
import ast
import asyncio
import datetime
import pathlib
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from policy.main import Decision, evaluate
from policy import main as policy_module


def extract(path, name, env):
    tree = ast.parse((ROOT / path).read_text(), filename=path)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 path, "exec"), env)
    return env[name]


class FakeTemporal:
    def __init__(self, synthetic=False):
        self.synthetic = synthetic
        self.calls = []

    async def execute_activity(self, name, args, **kw):
        self.calls.append(name)
        if name == "start_run":
            return {"version": 1}
        if name == "execute_stage" and args["stage"] == "HITL":
            if self.synthetic:
                return {"version": 2, "status": "PASS", "synthetic": True,
                        "execution_allowed": False, "effect_allowed": False}
            return {"version": 2, "status": "WAITING", "hitl_required": True,
                    "proposal_id": "ACT-OFFLINE", "proposal_hash": "hash-offline",
                    "proposal_revision": 1, "execution_allowed": False}
        if name == "execute_stage" and args["stage"] == "REMEDIATE" and self.synthetic:
            return {"version": 3, "status": "BLOCKED", "execution_allowed": False}
        raise AssertionError("unexpected_activity:" + name)

    async def wait_condition(self, predicate, **kw):
        if not predicate():
            raise AssertionError("no_offline_signal")


def workflow_class(fake, stages=("HITL", "REMEDIATE")):
    path = "app/worker/workflow.py"
    tree = ast.parse((ROOT / path).read_text(), filename=path)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "IncidentWorkflow")
    cls.decorator_list = []
    cls.bases = []
    cls.keywords = []
    cls.body = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name in ("__init__", "submit_hitl_decision", "run")]
    for n in cls.body:
        n.decorator_list = []
    env = {"workflow": fake, "datetime": datetime, "asyncio": asyncio,
           "STAGES": stages, "RETRY": object()}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 path, "exec"), env)
    return env["IncidentWorkflow"]


def signal(**kw):
    value = {"proposal_id": "ACT-OFFLINE", "proposal_hash": "hash-offline",
             "proposal_revision": 1, "decision": "REJECT"}
    value.update(kw)
    return value


def simulate(*signals, synthetic=False):
    fake = FakeTemporal(synthetic)
    obj = workflow_class(fake)()
    for item in signals:
        obj.submit_hitl_decision(item)
    result = asyncio.run(obj.run({"run_id": "RUN-OFFLINE",
                                  "mode": "DEMO" if synthetic else "LIVE",
                                  "scenario_id": "SCENARIO-OFFLINE"}))
    return result, fake.calls, obj


class OfflineFailureInjection(unittest.TestCase):
    def setUp(self):
        guard = patch.object(policy_module.autonomy_store, "status",
                             return_value={"mode": "NORMAL", "healthy": True})
        guard.start()
        self.addCleanup(guard.stop)

    def policy_input(self, **kw):
        data = dict(mode="DEMO", command="EXECUTE", severity="P2",
                    confidence=0.99, evidence_count=1, critic_validated=True,
                    redundancy_ok=True, evidence_fresh=True,
                    preconditions_verified=True, fencing_verified=True,
                    human_approved=False)
        data.update(kw)
        return Decision(**data)

    def test_policy_unknown(self):
        result = evaluate(self.policy_input(evidence_count=0))
        self.assertEqual((result["state"], result["decision"]), ("UNKNOWN", "HUMAN_APPROVAL"))

    def test_policy_block(self):
        result = evaluate(self.policy_input(mode="LIVE", severity="P1", human_approved=True))
        self.assertEqual((result["state"], result["decision"]), ("BLOCKED", "ESCALATE"))

    def test_policy_synthetic_never_live_allow(self):
        rejected = evaluate(self.policy_input(critic_validated=False))
        self.assertEqual((rejected["state"], rejected["decision"]), ("BLOCKED", "HUMAN_APPROVAL"))
        qualified = evaluate(self.policy_input())
        self.assertEqual((qualified["state"], qualified["decision"]), ("PASS", "SIMULATE"))

    def test_unknown_or_failed_critic_policy_stage_never_reaches_hitl(self):
        # Offline fake activities only. An UNKNOWN or non-PASS stage cannot
        # be treated as successful, even if a later HITL fixture says PASS.
        for stage in ("DGX_CRITIC", "POLICY"):
            for status in ("UNKNOWN", "FAIL", "REJECTED", "WAITING"):
                with self.subTest(stage=stage, status=status):
                    class NonPassingTemporal(FakeTemporal):
                        async def execute_activity(self, name, args, **kw):
                            if name == "execute_stage" and args["stage"] == stage:
                                self.calls.append(stage)
                                return {
                                    "version": 2, "status": status,
                                    "execution_allowed": False, "effect_allowed": False,
                                }
                            return await super().execute_activity(name, args, **kw)

                    fake = NonPassingTemporal(synthetic=True)
                    workflow = workflow_class(fake, stages=(stage, "HITL", "REMEDIATE"))()
                    receipt = asyncio.run(workflow.run({
                        "run_id": "RUN-OFFLINE", "mode": "DEMO",
                        "scenario_id": "SCENARIO-OFFLINE",
                    }))
                    self.assertEqual(receipt["status"], "BLOCKED")
                    self.assertEqual(receipt["reason"], "stage_not_passed")
                    self.assertIs(receipt["execution_allowed"], False)
                    self.assertIs(receipt["effect_allowed"], False)
                    self.assertEqual(fake.calls, ["start_run", stage])

    def test_unknown_mode_blocks_before_any_activity(self):
        # Policy SIMULATE is not a workflow mode. Do not start Core for a
        # malformed, forged or unrecognized mode.
        for mode in ("SIMULATE", "UNKNOWN", "", None, True, 1):
            with self.subTest(mode=repr(mode)):
                fake = FakeTemporal(synthetic=True)
                workflow = workflow_class(fake)()
                receipt = asyncio.run(workflow.run({
                    "run_id": "RUN-OFFLINE", "mode": mode,
                    "scenario_id": "SCENARIO-OFFLINE",
                }))
                self.assertEqual(receipt["reason"], "unsupported_workflow_mode")
                self.assertIs(receipt["execution_allowed"], False)
                self.assertIs(receipt["effect_allowed"], False)
                self.assertEqual(fake.calls, [])

    def test_critic_reject_prevents_proposal(self):
        for critique in ({"validated": False}, {"validated": True, "issues": ["unsafe"]}):
            with self.subTest(critique=critique):
                events = [
                    {"stage": "DGX_ANALYST", "event_type": "ANALYST_COMPLETED",
                     "status": "PASS", "payload": {"analysis": {"recommended_actions": []}}},
                    {"stage": "DGX_CRITIC", "event_type": "CRITIC_COMPLETED",
                     "status": "PASS", "payload": {"critique": critique}},
                ]
                post = Mock(side_effect=AssertionError("proposal_write_forbidden"))
                env = {"get_json": lambda *a, **k: {"events": events},
                       "post_json": post, "CORE": "offline", "ADMIN": "offline"}
                build = extract("app/worker/main.py", "create_hitl_proposal", env)
                self.assertEqual(build("RUN-OFFLINE", "DEMO", 1)["status"], "BLOCKED")
                post.assert_not_called()

    def test_reject_and_revoke_block(self):
        for item in (signal(), signal(source_status="REVOKED")):
            result, calls, _ = simulate(item)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["human_decision"], "REJECT")
            self.assertIs(result["execution_allowed"], False)
            self.assertEqual(calls, ["start_run", "execute_stage"])

    def test_duplicate_replay_idempotent(self):
        item = signal()
        result, calls, state = simulate(item, dict(item))
        self.assertFalse(state._hitl_conflict)
        self.assertIs(result["execution_allowed"], False)
        self.assertNotIn("finish_run", calls)

    def test_conflicting_signal_blocks(self):
        result, calls, state = simulate(signal(), signal(decision="APPROVE"))
        self.assertTrue(state._hitl_conflict)
        self.assertEqual(result["reason"], "hitl_timeout_or_conflicting_signal")
        self.assertIs(result["execution_allowed"], False)
        self.assertNotIn("finish_run", calls)

    def test_proposal_revision_mismatch_blocks(self):
        result, _, _ = simulate(signal(proposal_revision=2))
        self.assertEqual(result["reason"], "hitl_signal_scope_mismatch")
        self.assertIs(result["execution_allowed"], False)

    def test_offline_restart_replay(self):
        first, _, _ = simulate(signal())
        second, calls, _ = simulate(signal())
        self.assertEqual(first, second)
        self.assertNotIn("finish_run", calls)

    def test_matching_approve_signal_is_still_no_effect(self):
        # A matching Temporal signal is notification, never an execution grant.
        result, calls, state = simulate(signal(decision="APPROVE"))
        self.assertFalse(state._hitl_conflict)
        self.assertEqual(result["reason"], "human_decision_recorded_execution_gate_closed")
        self.assertEqual(result["human_decision"], "APPROVE")
        self.assertIs(result["execution_allowed"], False)
        self.assertEqual(calls, ["start_run", "execute_stage"])

    def test_stale_proposal_hash_signal_blocks_without_effect(self):
        result, calls, _ = simulate(signal(proposal_hash="stale-hash"))
        self.assertEqual(result["reason"], "hitl_signal_scope_mismatch")
        self.assertIs(result["execution_allowed"], False)
        self.assertNotIn("finish_run", calls)

    def test_offline_worker_restart_without_replayed_signal_times_out_closed(self):
        # Fresh workflow instance with lost notification: offline timeout emulation,
        # NOT a real Temporal replay/restart or PostgreSQL integration test.
        class LostSignalTemporal(FakeTemporal):
            async def wait_condition(self, predicate, **kw):
                if predicate():
                    raise AssertionError("unexpected_persisted_signal")
                raise asyncio.TimeoutError

        fake = LostSignalTemporal()
        restarted = workflow_class(fake)()
        result = asyncio.run(restarted.run({
            "run_id": "RUN-OFFLINE", "mode": "LIVE",
            "scenario_id": "SCENARIO-OFFLINE",
        }))
        self.assertEqual(result["reason"], "hitl_timeout_or_conflicting_signal")
        self.assertIs(result["execution_allowed"], False)
        self.assertEqual(fake.calls, ["start_run", "execute_stage"])

    def test_synthetic_human_signal_is_not_authority(self):
        result, calls, _ = simulate(signal(decision="APPROVE"), synthetic=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(calls, ["start_run", "execute_stage", "execute_stage"])

    def test_invalid_revision_types_and_values_fail_closed(self):
        # Python True == 1 and 1.0 == 1 must not bind to a persisted revision.
        for invalid in (True, 1.0, "1", None, 0, -1):
            with self.subTest(revision=repr(invalid)):
                result, calls, state = simulate(signal(proposal_revision=invalid))
                self.assertTrue(state._hitl_conflict)
                self.assertEqual(result["reason"], "hitl_timeout_or_conflicting_signal")
                self.assertIs(result["execution_allowed"], False)
                self.assertNotIn("finish_run", calls)

    def test_replayed_boolean_revision_fails_binding_even_if_signal_gate_bypassed(self):
        fake = FakeTemporal()
        obj = workflow_class(fake)()
        # Simulate stale/replayed state loaded without the current signal validator.
        obj._hitl_decision = signal(proposal_revision=True)
        result = asyncio.run(obj.run({
            "run_id": "RUN-OFFLINE", "mode": "LIVE",
            "scenario_id": "SCENARIO-OFFLINE",
        }))
        self.assertEqual(result["reason"], "hitl_signal_scope_mismatch")
        self.assertIs(result["execution_allowed"], False)
        self.assertNotIn("finish_run", fake.calls)


    def test_synthetic_blocked_stage_has_explicit_no_effect_receipt(self):
        # Offline AST/fake Temporal only: no network, executor or real activity.
        result, calls, _ = simulate(synthetic=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIs(result["execution_allowed"], False)
        self.assertNotIn("finish_run", calls)

    def test_synthetic_completed_run_has_explicit_no_effect_receipt(self):
        # A successful synthetic stage chain must not imply execution authority.
        class CompletedSyntheticTemporal(FakeTemporal):
            async def execute_activity(self, name, args, **kw):
                if name == "execute_stage" and args["stage"] == "REMEDIATE":
                    self.calls.append(name)
                    return {"version": 3, "status": "PASS", "execution_allowed": False}
                if name == "finish_run":
                    self.calls.append(name)
                    return {"version": 4, "status": "COMPLETED"}
                return await super().execute_activity(name, args, **kw)

        fake = CompletedSyntheticTemporal(synthetic=True)
        obj = workflow_class(fake)()
        result = asyncio.run(obj.run({
            "run_id": "RUN-OFFLINE", "mode": "DEMO",
            "scenario_id": "SCENARIO-OFFLINE",
        }))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIs(result["execution_allowed"], False)
        self.assertEqual(fake.calls, ["start_run", "execute_stage", "execute_stage", "finish_run"])


    def test_revoked_approval_signal_conflict_stays_blocked(self):
        # A subsequent committed revoke is a REJECT notification, not a grant.
        result, calls, state = simulate(
            signal(decision="APPROVE", source_status="APPROVED"),
            signal(decision="REJECT", source_status="REVOKED"),
        )
        self.assertTrue(state._hitl_conflict)
        self.assertEqual(result["reason"], "hitl_timeout_or_conflicting_signal")
        self.assertIs(result["execution_allowed"], False)
        self.assertIs(result["effect_allowed"], False)
        self.assertEqual(calls, ["start_run", "execute_stage"])

    def test_forged_temporal_actor_tenant_mfa_cannot_authorize(self):
        # A signal may carry untrusted identity/scope claims; none authorize.
        forged = signal(
            decision="APPROVE", actor_id="oidc:synthetic-fixture",
            tenant_id="OTHER-TENANT", target_ci_id="OTHER-CI",
            mfa=True, execution_allowed=True, effect_allowed=True,
        )
        result, calls, _ = simulate(forged)
        self.assertEqual(result["reason"], "human_decision_recorded_execution_gate_closed")
        self.assertIs(result["execution_allowed"], False)
        self.assertIs(result["effect_allowed"], False)
        self.assertNotIn("REMEDIATE", calls)
        self.assertNotIn("finish_run", calls)

    def test_every_temporal_workflow_return_explicitly_fences_effects(self):
        # Static contract: all final return paths deny both execution and effects.
        tree = ast.parse((ROOT / "app/worker/workflow.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == "IncidentWorkflow")
        run = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef)
                   and n.name == "run")
        returns = [n.value for n in ast.walk(run) if isinstance(n, ast.Return)]
        self.assertGreaterEqual(len(returns), 9)
        for receipt in returns:
            self.assertIsInstance(receipt, ast.Dict)
            fields = {key.value: value for key, value in zip(receipt.keys, receipt.values)
                      if isinstance(key, ast.Constant) and isinstance(key.value, str)}
            for flag in ("execution_allowed", "effect_allowed"):
                self.assertIn(flag, fields)
                self.assertIsInstance(fields[flag], ast.Constant)
                self.assertIs(fields[flag].value, False)


    def test_synthetic_hitl_forged_effect_flag_blocks_before_remediation(self):
        # Synthetic HITL receipts cannot claim effects, even with PASS status.
        class ForgedEffectTemporal(FakeTemporal):
            async def execute_activity(self, name, args, **kw):
                if name == "execute_stage" and args["stage"] == "HITL":
                    self.calls.append(name)
                    return {"version": 2, "status": "PASS", "synthetic": True,
                            "execution_allowed": False, "effect_allowed": True}
                return await super().execute_activity(name, args, **kw)

        fake = ForgedEffectTemporal(synthetic=True)
        result = asyncio.run(workflow_class(fake)().run({
            "run_id": "RUN-OFFLINE", "mode": "DEMO",
            "scenario_id": "SCENARIO-OFFLINE",
        }))
        self.assertEqual(result["reason"], "synthetic_hitl_bypass_contract_invalid")
        self.assertIs(result["execution_allowed"], False)
        self.assertIs(result["effect_allowed"], False)
        self.assertEqual(fake.calls, ["start_run", "execute_stage"])

    def test_synthetic_hitl_missing_effect_flag_fails_closed(self):
        # Missing provenance is not a false value; reject absent effect fence.
        class MissingEffectTemporal(FakeTemporal):
            async def execute_activity(self, name, args, **kw):
                if name == "execute_stage" and args["stage"] == "HITL":
                    self.calls.append(name)
                    return {"version": 2, "status": "PASS", "synthetic": True,
                            "execution_allowed": False}
                return await super().execute_activity(name, args, **kw)

        fake = MissingEffectTemporal(synthetic=True)
        result = asyncio.run(workflow_class(fake)().run({
            "run_id": "RUN-OFFLINE", "mode": "DEMO",
            "scenario_id": "SCENARIO-OFFLINE",
        }))
        self.assertEqual(result["reason"], "synthetic_hitl_bypass_contract_invalid")
        self.assertIs(result["execution_allowed"], False)
        self.assertIs(result["effect_allowed"], False)
        self.assertEqual(fake.calls, ["start_run", "execute_stage"])



if __name__ == "__main__":
    unittest.main()
