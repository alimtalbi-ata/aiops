"""ACME policy scenario walkthrough, entirely isolated and non-executing."""
import json
from policy import autonomy_store as store
from policy.execution_fence import reserve,summary,decisions
from policy.step_guard import validate_step

def run_simulation():
    events=[]
    def record(stage,**values):events.append({"step":stage,**values})
    initial=store.status()
    if not initial["healthy"] or initial["revision"]!=0 or initial["mode"]!="STOP_AUTO":
        raise RuntimeError("isolated empty policy database required")
    normal=store.set_mode("NORMAL","acme-demo-harness","Synthetic demonstration of initial normal policy",0)
    record("MODE_NORMAL_SIMULATED",mode=normal["mode"],revision=normal["revision"])
    proposal={"operation_id":"ACME-SIM-PAYROLL-LB-RESTART","operation_class":"AUTONOMOUS_REMEDIATION",
        "description":"Proposed restart of synthetic payroll load balancer","execution_allowed":False}
    record("AI_PROPOSAL",**proposal)
    admission=reserve(proposal["operation_id"],normal["revision"],proposal["operation_class"])
    record("POLICY_RESERVATION",**admission)
    if not admission["admitted"]:raise RuntimeError("test reservation not admitted")
    emergency=store.set_mode("STOP_AUTO","acme-demo-operator","Synthetic emergency stop during payroll incident",normal["revision"])
    record("STOP_AUTO_SIMULATED",mode=emergency["mode"],revision=emergency["revision"])
    final=validate_step(proposal["operation_id"],normal["revision"])
    record("FINAL_POLICY_CHECK",**final)
    if final["valid"] or final["execution_allowed"]:raise RuntimeError("simulation guard bypass")
    record("HUMAN_NOTIFICATION_SIMULATED",message="Management approval required; no restart executed")
    result={"scope":"ACME","simulation_only":True,"model_inference_performed":False,
        "live_effects":0,"events":events,"policy_history":store.history(),
        "policy_kpis":summary(),"decision_audit":decisions()}
    return result
