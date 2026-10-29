"""Deterministic Temporal workflow definition.

No FastAPI, HTTP client, database, OS IO or provider integration imports are
allowed here. All side effects are executed by separately registered activities
inside worker.main. The sandbox re-imports *this module*, not worker.main.
"""
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
        result = await workflow.execute_activity(
            "finish_run",
            {"run_id": run_id, "version": version},
            start_to_close_timeout=datetime.timedelta(seconds=30),
            retry_policy=RETRY,
            result_type=dict,
        )
        return {"run_id": run_id, "status": result["status"], "final_version": result["version"]}
