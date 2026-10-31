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
            return {"run_id": "RUN-OFFLINE", "version": 1, "status": "RUNNING",
                    "execution_allowed": False, "effect_allowed": False}
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
                    return {"version": 3, "status": "PASS", "execution_allowed": False,
                            "effect_allowed": False}
                if name == "finish_run":
                    self.calls.append(name)
                    return {"run_id": "RUN-OFFLINE", "version": 4,
                            "status": "RESOLVED", "execution_allowed": False,
                            "effect_allowed": False}
                return await super().execute_activity(name, args, **kw)

        fake = CompletedSyntheticTemporal(synthetic=True)
        obj = workflow_class(fake)()
        result = asyncio.run(obj.run({
            "run_id": "RUN-OFFLINE", "mode": "DEMO",
            "scenario_id": "SCENARIO-OFFLINE",
        }))
        self.assertEqual(result["status"], "RESOLVED")
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



    def test_core_statusless_stage_ack_is_explicitly_no_effect(self):
        # Core /events acknowledges version/sequence, not event status.
        # The Worker may attach PASS only after its own known PASS event.
        # No HTTP, database, provider, Temporal service or LIVE run.
        events = []
        def fake_call(method, url, payload):
            self.assertEqual(method, "POST")
            events.append(payload["event_type"])
            if payload["event_type"] == "STAGE_STARTED":
                return {"run_id": "RUN-OFFLINE", "sequence": 1, "version": 2}
            if payload["event_type"] == "STAGE_COMPLETED":
                return {"run_id": "RUN-OFFLINE", "sequence": 2, "version": 3}
            raise AssertionError("unexpected_core_call")

        def fake_post(base, path, payload, **kwargs):
            if base == "EVID" and path == "/api/evidence":
                return {"evidence_id": "E-OFFLINE"}
            if base == "CORE" and (path.endswith("/checkpoint")
                                   or path.endswith("/demo-artifacts")):
                return {}
            raise AssertionError("unexpected_post")

        env = {"CORE": "CORE", "EVID": "EVID", "ADMIN": "offline",
               "call": fake_call, "post_json": fake_post}
        env["verified_no_effect_stage_receipt"] = extract(
            "app/worker/main.py", "verified_no_effect_stage_receipt", env)
        env["verified_no_effect_stage_started_receipt"] = extract(
            "app/worker/main.py", "verified_no_effect_stage_started_receipt", env)
        stage = extract("app/worker/main.py", "_execute_stage_blocking", env)
        receipt = stage({
            "run_id": "RUN-OFFLINE", "version": 1,
            "stage": "NORMALIZE", "mode": "DEMO",
            "scenario_id": "SCENARIO-OFFLINE",
        }, 1)
        self.assertEqual(events, ["STAGE_STARTED", "STAGE_COMPLETED"])
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["version"], 3)
        self.assertIs(receipt["execution_allowed"], False)
        self.assertIs(receipt["effect_allowed"], False)

    def test_stage_ack_fencing_rejects_stale_or_effect_authority(self):
        # Isolated forged Core ACKs cannot become PASS or authorize effects.
        normalize = extract("app/worker/main.py",
                            "verified_no_effect_stage_receipt", {})
        base = {"run_id": "RUN-OFFLINE", "sequence": 2, "version": 3}
        mutations = (
            {"run_id": "RUN-OTHER"},
            {"version": 2},
            {"version": True},
            {"version": 2.0},
            {"version": None},
            {"status": "BLOCKED"},
            {"status": "UNKNOWN"},
            {"execution_allowed": True},
            {"effect_allowed": True},
            {"execution_allowed": 1},
            {"effect_allowed": 1},
            {"sequence": None},
            {"sequence": True},
            {"sequence": 2.0},
            {"sequence": "2"},
            {"sequence": 0},
            {"sequence": -1},
            {"stage": "HITL"},
        )
        for change in mutations:
            with self.subTest(change=change):
                with self.assertRaisesRegex(
                        RuntimeError, "stage_pass_receipt_not_qualified"):
                    normalize({**base, **change}, "RUN-OFFLINE", "NORMALIZE", 2)


    def test_stage_ack_missing_sequence_cannot_be_promoted(self):
        # A Core ACK with a fresh version but no event sequence is unverified.
        # This is an AST-only invocation, not a Core or Temporal request.
        normalize = extract("app/worker/main.py",
                            "verified_no_effect_stage_receipt", {})
        with self.assertRaisesRegex(RuntimeError, "stage_pass_receipt_not_qualified"):
            normalize({"run_id": "RUN-OFFLINE", "version": 3},
                      "RUN-OFFLINE", "NORMALIZE", 2)

    def test_non_hitl_pass_requires_explicit_no_effect_fences(self):
        # A forged PASS for any earlier stage must not reach HITL or REMEDIATE.
        # All activities are in-memory fakes, with no LIVE execution.
        for fields in (
            {},
            {"execution_allowed": False},
            {"effect_allowed": False},
            {"execution_allowed": True, "effect_allowed": False},
            {"execution_allowed": False, "effect_allowed": True},
            {"execution_allowed": 0, "effect_allowed": False},
        ):
            with self.subTest(fields=fields):
                class ForgedPassTemporal(FakeTemporal):
                    async def execute_activity(self, name, args, **kw):
                        if name == "execute_stage" and args["stage"] == "NORMALIZE":
                            self.calls.append(name)
                            return {"version": 2, "status": "PASS", **fields}
                        return await super().execute_activity(name, args, **kw)

                fake = ForgedPassTemporal(synthetic=True)
                result = asyncio.run(workflow_class(
                    fake, stages=("NORMALIZE", "HITL", "REMEDIATE"))().run({
                        "run_id": "RUN-OFFLINE", "mode": "DEMO",
                        "scenario_id": "SCENARIO-OFFLINE",
                    }))
                self.assertEqual(result["reason"],
                                 "stage_effect_fence_missing_or_invalid")
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["effect_allowed"], False)
                self.assertEqual(fake.calls, ["start_run", "execute_stage"])



    def test_core_command_ack_fencing_start_and_resolve(self):
        # Core command receipts are not permission grants, even on idempotent replay.
        # This invokes an isolated AST function only, without network or DB.
        normalize = extract("app/worker/main.py",
                            "verified_no_effect_command_receipt", {})
        for command, status, previous in (
            ("START", "RUNNING", 1), ("RESOLVE", "RESOLVED", 3),
        ):
            with self.subTest(command=command):
                base = {"run_id": "RUN-OFFLINE", "status": status,
                        "version": previous + 1}
                result = normalize(base, "RUN-OFFLINE", command, previous)
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["effect_allowed"], False)
                for mutation in (
                    {"run_id": "RUN-OTHER"},
                    {"status": "PASS"},
                    {"status": "BLOCKED"},
                    {"version": previous},
                    {"version": True},
                    {"version": float(previous + 1)},
                    {"execution_allowed": True},
                    {"effect_allowed": True},
                    {"execution_allowed": 1},
                    {"effect_allowed": 1},
                ):
                    with self.subTest(mutation=mutation):
                        with self.assertRaisesRegex(
                                RuntimeError, "command_receipt_not_qualified"):
                            normalize({**base, **mutation},
                                      "RUN-OFFLINE", command, previous)
                with self.assertRaisesRegex(
                        RuntimeError, "command_receipt_not_qualified"):
                    normalize(base, "RUN-OFFLINE", command, True)

    def test_temporal_forged_start_receipt_blocks_before_any_stage(self):
        # An activity ACK with missing/forged effect flags is not trusted.
        for mutation in (
            {"effect_allowed": True},
            {"execution_allowed": True},
            {"effect_allowed": None},
            {"execution_allowed": None},
            {"run_id": "RUN-OTHER"},
            {"status": "PASS"},
            {"version": True},
        ):
            with self.subTest(mutation=mutation):
                class ForgedStart(FakeTemporal):
                    async def execute_activity(self, name, args, **kw):
                        if name == "start_run":
                            base = await super().execute_activity(name, args, **kw)
                            return {**base, **mutation}
                        return await super().execute_activity(name, args, **kw)

                fake = ForgedStart(synthetic=True)
                result = asyncio.run(workflow_class(fake)().run({
                    "run_id": "RUN-OFFLINE", "mode": "DEMO",
                    "scenario_id": "SCENARIO-OFFLINE",
                }))
                self.assertEqual(result["reason"], "start_receipt_not_qualified")
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["effect_allowed"], False)
                self.assertEqual(fake.calls, ["start_run"])

    def test_temporal_forged_finish_receipt_blocks_resolution(self):
        # The final command cannot fabricate success or authorize an effect.
        for mutation in (
            {"effect_allowed": True},
            {"execution_allowed": True},
            {"effect_allowed": None},
            {"run_id": "RUN-OTHER"},
            {"status": "COMPLETED"},
            {"version": 2},
            {"version": 3.0},
        ):
            with self.subTest(mutation=mutation):
                class ForgedFinish(FakeTemporal):
                    async def execute_activity(self, name, args, **kw):
                        if name == "finish_run":
                            self.calls.append(name)
                            return {
                                "run_id": "RUN-OFFLINE", "status": "RESOLVED",
                                "version": 3, "execution_allowed": False,
                                "effect_allowed": False, **mutation,
                            }
                        return await super().execute_activity(name, args, **kw)

                fake = ForgedFinish(synthetic=True)
                result = asyncio.run(workflow_class(
                    fake, stages=("HITL",))().run({
                        "run_id": "RUN-OFFLINE", "mode": "DEMO",
                        "scenario_id": "SCENARIO-OFFLINE",
                    }))
                self.assertEqual(result["reason"], "finish_receipt_not_qualified")
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["effect_allowed"], False)
                self.assertEqual(fake.calls, ["start_run", "execute_stage", "finish_run"])


    def test_stage_pass_ack_rejects_skipped_version_or_forged_event(self):
        # Offline Core receipt mutations. A statusless ACK is not a
        # free-standing PASS decision and cannot skip a committed version.
        normalize = extract("app/worker/main.py",
                            "verified_no_effect_stage_receipt", {})
        base = {"run_id": "RUN-OFFLINE", "sequence": 2, "version": 3}
        for mutation in (
            {"version": 4}, {"version": 999},
            {"event_type": "STAGE_FAILED"},
            {"event_type": "HITL_PROPOSAL_CREATED"},
            {"idempotent": "yes"}, {"idempotent": 1},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(
                        RuntimeError, "stage_pass_receipt_not_qualified"):
                    normalize({**base, **mutation},
                              "RUN-OFFLINE", "NORMALIZE", 2)
        valid = normalize({**base, "event_type": "STAGE_COMPLETED",
                           "idempotent": False},
                          "RUN-OFFLINE", "NORMALIZE", 2)
        self.assertIs(valid["execution_allowed"], False)
        self.assertIs(valid["effect_allowed"], False)

    def test_forged_stage_pass_ack_blocks_checkpoint_and_demo_artifacts(self):
        # Exercise the real stage function with fake Core/Evidence calls.
        # A forged completion ACK may record STAGE_FAILED but must not
        # trigger a checkpoint or synthetic demo artifact after rejection.
        for mutation in (
            {"version": 4}, {"event_type": "STAGE_FAILED"},
            {"idempotent": "forged"}, {"effect_allowed": True},
            {"run_id": "RUN-OTHER"}, {"status": "BLOCKED"},
        ):
            with self.subTest(mutation=mutation):
                calls, writes = [], []

                def fake_call(method, url, payload):
                    event = payload["event_type"]
                    calls.append(event)
                    if event == "STAGE_STARTED":
                        return {"run_id": "RUN-OFFLINE",
                                "sequence": 1, "version": 2}
                    if event == "STAGE_COMPLETED":
                        return {"run_id": "RUN-OFFLINE",
                                "sequence": 2, "version": 3, **mutation}
                    if event == "STAGE_FAILED":
                        return {"run_id": "RUN-OFFLINE",
                                "sequence": 3, "version": 4}
                    raise AssertionError("unexpected_core_call")

                def fake_post(base, path, payload, **kwargs):
                    writes.append((base, path))
                    if base == "EVID" and path == "/api/evidence":
                        return {"evidence_id": "E-OFFLINE"}
                    if base == "CORE" and (
                            path.endswith("/checkpoint")
                            or path.endswith("/demo-artifacts")):
                        raise AssertionError("unverified_ack_promoted")
                    raise AssertionError("unexpected_post")

                env = {"CORE": "CORE", "EVID": "EVID", "ADMIN": "offline",
                       "call": fake_call, "post_json": fake_post}
                env["verified_no_effect_stage_receipt"] = extract(
                    "app/worker/main.py", "verified_no_effect_stage_receipt", env)
                env["verified_no_effect_stage_started_receipt"] = extract(
                    "app/worker/main.py", "verified_no_effect_stage_started_receipt", env)
                stage = extract("app/worker/main.py", "_execute_stage_blocking", env)
                with self.assertRaisesRegex(
                        RuntimeError, "stage_pass_receipt_not_qualified"):
                    stage({"run_id": "RUN-OFFLINE", "version": 1,
                           "stage": "NORMALIZE", "mode": "DEMO",
                           "scenario_id": "SCENARIO-OFFLINE"}, 1)
                self.assertEqual(calls,
                                 ["STAGE_STARTED", "STAGE_COMPLETED", "STAGE_FAILED"])
                self.assertEqual(writes, [("EVID", "/api/evidence")])


    def test_synthetic_hitl_skip_ack_mutations_never_checkpoint(self):
        # Fake Core ACKs only. No HTTP, DB, Temporal service or LIVE execution.
        # The Core statusless event ACK is not itself a Policy/HITL grant.
        mutations = (
            {"run_id": "RUN-OTHER"},
            {"version": 2}, {"version": 4}, {"version": True},
            {"sequence": None}, {"sequence": 0}, {"sequence": True},
            {"stage": "POLICY"}, {"event_type": "STAGE_COMPLETED"},
            {"event_type": "HITL_PROPOSAL_CREATED"},
            {"status": "BLOCKED"}, {"status": "UNKNOWN"},
            {"effect_allowed": True}, {"execution_allowed": True},
            {"idempotent": "yes"},
        )
        for mode in ("DEMO", "REPLAY", "STORY"):
            for mutation in mutations:
                with self.subTest(mode=mode, mutation=mutation):
                    calls, checkpoints = [], []

                    def fake_call(method, url, payload):
                        kind = payload["event_type"]
                        calls.append(kind)
                        if kind == "STAGE_STARTED":
                            return {"run_id": "RUN-OFFLINE",
                                    "sequence": 1, "version": 2}
                        if kind == "HITL_SIMULATION_SKIPPED":
                            return {"run_id": "RUN-OFFLINE",
                                    "sequence": 2, "version": 3, **mutation}
                        if kind == "STAGE_FAILED":
                            return {"run_id": "RUN-OFFLINE",
                                    "sequence": 3, "version": 4}
                        raise AssertionError("unexpected_core_call")

                    def fake_post(base, path, payload, **kwargs):
                        checkpoints.append(path)
                        raise AssertionError("unqualified_hitl_ack_checkpoint")

                    env = {"CORE": "CORE", "ADMIN": "offline",
                           "call": fake_call, "post_json": fake_post}
                    env["verified_no_effect_stage_receipt"] = extract(
                        "app/worker/main.py", "verified_no_effect_stage_receipt", env)
                    env["verified_no_effect_stage_started_receipt"] = extract(
                        "app/worker/main.py", "verified_no_effect_stage_started_receipt", env)
                    stage = extract("app/worker/main.py", "_execute_stage_blocking", env)
                    with self.assertRaisesRegex(
                            RuntimeError, "stage_pass_receipt_not_qualified"):
                        stage({"run_id": "RUN-OFFLINE", "version": 1,
                               "stage": "HITL", "mode": mode,
                               "scenario_id": "SCENARIO-OFFLINE"}, 1)
                    self.assertEqual(calls, ["STAGE_STARTED",
                                             "HITL_SIMULATION_SKIPPED",
                                             "STAGE_FAILED"])
                    self.assertEqual(checkpoints, [])

    def test_synthetic_hitl_skip_valid_ack_is_explicit_no_effect(self):
        # A valid statusless ACK can only yield a synthetic no-effect receipt.
        for mode in ("DEMO", "REPLAY", "STORY"):
            with self.subTest(mode=mode):
                calls, checkpoints = [], []

                def fake_call(method, url, payload):
                    kind = payload["event_type"]
                    calls.append(kind)
                    if kind == "STAGE_STARTED":
                        return {"run_id": "RUN-OFFLINE",
                                "sequence": 1, "version": 2}
                    if kind == "HITL_SIMULATION_SKIPPED":
                        self.assertIs(payload["payload"]["execution_allowed"], False)
                        self.assertIs(payload["payload"]["effect_allowed"], False)
                        return {"run_id": "RUN-OFFLINE", "sequence": 2,
                                "version": 3, "event_type": kind}
                    raise AssertionError("unexpected_core_call")

                def fake_post(base, path, payload, **kwargs):
                    self.assertEqual(base, "CORE")
                    checkpoints.append((path, payload))
                    return {}

                env = {"CORE": "CORE", "ADMIN": "offline",
                       "call": fake_call, "post_json": fake_post}
                env["verified_no_effect_stage_receipt"] = extract(
                    "app/worker/main.py", "verified_no_effect_stage_receipt", env)
                env["verified_no_effect_stage_started_receipt"] = extract(
                    "app/worker/main.py", "verified_no_effect_stage_started_receipt", env)
                stage = extract("app/worker/main.py", "_execute_stage_blocking", env)
                result = stage({"run_id": "RUN-OFFLINE", "version": 1,
                                "stage": "HITL", "mode": mode,
                                "scenario_id": "SCENARIO-OFFLINE"}, 1)
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["version"], 3)
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["effect_allowed"], False)
                self.assertEqual(calls, ["STAGE_STARTED", "HITL_SIMULATION_SKIPPED"])
                self.assertEqual(checkpoints, [
                    ("/api/runs/RUN-OFFLINE/checkpoint",
                     {"stage": "HITL", "version": 3})])


if __name__ == "__main__":
    unittest.main()
