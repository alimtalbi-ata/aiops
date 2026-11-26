"""First isolated V3 orchestration boundary: no business stage is certified."""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY=RetryPolicy(initial_interval=timedelta(seconds=1),maximum_attempts=3)

@workflow.defn
class V3BoundaryWorkflow:
    @workflow.run
    async def run(self,args):
        started=await workflow.execute_activity("v3_boundary_start",args,result_type=dict,start_to_close_timeout=timedelta(seconds=30),retry_policy=RETRY)
        blocked=await workflow.execute_activity("v3_boundary_block",{**args,"version":started["version"]},result_type=dict,start_to_close_timeout=timedelta(seconds=30),retry_policy=RETRY)
        return {"run_id":args["run_id"],"status":blocked["status"],"final_version":blocked["version"],
                "reason":"V3_STAGE_ADAPTERS_NOT_QUALIFIED","executed_on_host":False,"production_authorized":False}
