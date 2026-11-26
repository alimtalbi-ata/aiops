"""Dedicated E17 lab workflow; no generic command, no automatic action retry."""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class E17LabRecoveryWorkflow:
    @workflow.run
    async def run(self, approval: dict) -> dict:
        return await workflow.execute_activity(
            "v3_e17_reset_lab_http_delay", approval, result_type=dict,
            start_to_close_timeout=timedelta(seconds=30),
            schedule_to_close_timeout=timedelta(seconds=45),
            retry_policy=RetryPolicy(maximum_attempts=1))
