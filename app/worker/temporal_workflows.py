"""Deterministic Temporal workflow definitions; no HTTP/GLPI/Worker imports.

Activities run outside the workflow sandbox. The workflow itself only schedules
registered activity names and records their redacted results.
"""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

STAGES = [
    "NORMALIZE", "CORRELATE", "CMDB", "OBSERVE", "RAG", "DGX_ANALYST",
    "DGX_CRITIC", "POLICY", "HITL", "REMEDIATE", "VERIFY", "RECONCILE", "LEARN",
]
RETRY = RetryPolicy(initial_interval=timedelta(seconds=1),
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(seconds=10),
                    maximum_attempts=3)


@workflow.defn
class IncidentWorkflow:
    @workflow.run
    async def run(self, args):
        result = await workflow.execute_activity(
            "start_run", args, start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY)
        version = result["version"]
        for stage in STAGES:
            result = await workflow.execute_activity(
                "execute_stage", {
                    "stage": stage, "run_id": args["run_id"], "version": version,
                    "mode": args["mode"], "scenario_id": args["scenario_id"],
                }, start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RETRY)
            version = result["version"]
            if result.get("status") == "BLOCKED":
                return {"run_id": args["run_id"], "status": "BLOCKED",
                        "final_version": version}
        final = await workflow.execute_activity(
            "finish_run", {"run_id": args["run_id"], "version": version},
            start_to_close_timeout=timedelta(seconds=30), retry_policy=RETRY)
        return {"run_id": args["run_id"], "final_version": final["version"],
                "status": final["status"]}


@workflow.defn
class TerminalRejectWorkflow:
    @workflow.run
    async def run(self, args):
        return await workflow.execute_activity(
            "reject_terminal_recover", args,
            start_to_close_timeout=timedelta(seconds=60), retry_policy=RETRY)


@workflow.defn
class AcmeSimulatedHitlWorkflow:
    """Sandbox-only no-effect activity; Temporal persists the redacted audit."""

    @workflow.run
    async def run(self, intent):
        return await workflow.execute_activity(
            "acme_simulated_no_effect", intent,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=1))
