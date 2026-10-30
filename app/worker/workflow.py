"""Deterministic Temporal workflow definition.

No FastAPI, HTTP client, database, OS IO or provider integration imports are
allowed here. All side effects are executed by separately registered activities
inside worker.main. The sandbox re-imports *this module*, not worker.main.
"""
import asyncio
import datetime

from temporalio import workflow
from temporalio.common import RetryPolicy

STAGES = (
    "NORMALIZE", "CORRELATE", "CMDB", "OBSERVE", "RAG",
    "DGX_ANALYST", "DGX_CRITIC", "POLICY", "HITL",
    "REMEDIATE", "VERIFY", "RECONCILE", "LEARN",
)
RETRY = RetryPolicy(
    initial_interval=datetime.timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=datetime.timedelta(seconds=10),
    maximum_attempts=3,
)


@workflow.defn
class IncidentWorkflow:
    def __init__(self):
        self._hitl_decision = None
        self._hitl_conflict = False

    @workflow.signal
    def submit_hitl_decision(self, decision: dict) -> None:
        """Accept one immutable decision binding; conflicting retries fail closed."""
        if not isinstance(decision, dict):
            self._hitl_conflict = True
            return
        required = ("proposal_id", "proposal_hash", "proposal_revision", "decision")
        if any(key not in decision for key in required):
            self._hitl_conflict = True
            return
        if decision.get("decision") not in ("APPROVE", "REJECT"):
            self._hitl_conflict = True
            return
        if self._hitl_decision is None:
            self._hitl_decision = dict(decision)
        elif self._hitl_decision != decision:
            self._hitl_conflict = True

    @workflow.run
    async def run(self, args: dict) -> dict:
        run_id = args["run_id"]
        receipt = await workflow.execute_activity(
            "start_run",
            args,
            start_to_close_timeout=datetime.timedelta(seconds=30),
            retry_policy=RETRY,
            result_type=dict,
        )
        version = receipt["version"]
        for stage in STAGES:
            receipt = await workflow.execute_activity(
                "execute_stage",
                {
                    "stage": stage,
                    "run_id": run_id,
                    "version": version,
                    "mode": args["mode"],
                    "scenario_id": args["scenario_id"],
                },
                start_to_close_timeout=datetime.timedelta(seconds=180),
                retry_policy=RETRY,
                result_type=dict,
            )
            version = receipt["version"]
            if receipt.get("status") == "BLOCKED":
                return {"run_id": run_id, "status": "BLOCKED", "final_version": version}

            # HITL is a mandatory barrier before every remediation stage.
            # A generic PASS from an unimplemented/failed proposal activity must
            # never let the workflow fall through to REMEDIATE.
            if stage == "HITL" and not (
                receipt.get("status") == "WAITING" or receipt.get("hitl_required") is True
            ):
                return {
                    "run_id": run_id, "status": "BLOCKED",
                    "final_version": version,
                    "reason": "hitl_proposal_not_persisted",
                    "execution_allowed": False,
                }

            # A durable wait is allowed only with a persisted proposal binding.
            # A browser signal alone is never execution authority.
            if stage == "HITL":
                proposal_id = receipt.get("proposal_id")
                proposal_hash = receipt.get("proposal_hash")
                revision = receipt.get("proposal_revision")
                if not proposal_id or not proposal_hash or type(revision) is not int:
                    return {
                        "run_id": run_id, "status": "BLOCKED",
                        "final_version": version, "reason": "hitl_proposal_binding_missing",
                        "execution_allowed": False,
                    }
                timeout_seconds = args.get("hitl_timeout_seconds", 86400)
                if type(timeout_seconds) is not int or not 60 <= timeout_seconds <= 604800:
                    timeout_seconds = 86400
                try:
                    await workflow.wait_condition(
                        lambda: self._hitl_decision is not None or self._hitl_conflict,
                        timeout=datetime.timedelta(seconds=timeout_seconds),
                    )
                except asyncio.TimeoutError:
                    return {
                        "run_id": run_id, "status": "BLOCKED",
                        "final_version": version,
                        "reason": "hitl_timeout_or_conflicting_signal",
                        "execution_allowed": False,
                    }
                if self._hitl_conflict or self._hitl_decision is None:
                    return {
                        "run_id": run_id, "status": "BLOCKED",
                        "final_version": version,
                        "reason": "hitl_timeout_or_conflicting_signal",
                        "execution_allowed": False,
                    }
                decision = self._hitl_decision
                if (
                    decision.get("proposal_id") != proposal_id
                    or decision.get("proposal_hash") != proposal_hash
                    or decision.get("proposal_revision") != revision
                ):
                    return {
                        "run_id": run_id, "status": "BLOCKED",
                        "final_version": version, "reason": "hitl_signal_scope_mismatch",
                        "execution_allowed": False,
                    }
                # Human approval is recorded, but Policy/executor qualification
                # is not complete in this release. Never advance to REMEDIATE.
                return {
                    "run_id": run_id, "status": "BLOCKED",
                    "final_version": version,
                    "reason": "human_decision_recorded_execution_gate_closed",
                    "human_decision": decision.get("decision"),
                    "execution_allowed": False,
                }
        result = await workflow.execute_activity(
            "finish_run",
            {"run_id": run_id, "version": version},
            start_to_close_timeout=datetime.timedelta(seconds=30),
            retry_policy=RETRY,
            result_type=dict,
        )
        return {"run_id": run_id, "status": result["status"], "final_version": result["version"]}
