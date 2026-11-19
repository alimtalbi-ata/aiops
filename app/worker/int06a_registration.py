"""Explicit opt-in registration; absent server authorities remain fail closed."""
from temporalio import activity
from temporalio.exceptions import ApplicationError
from worker.acme_simulated_hitl import validate_intent
from worker.int06a_contract import refuse_unattested_context

@activity.defn
async def acme_no_effect_activity(intent):
    validate_intent(intent)
    # No authenticated attempt readback endpoints exist in this baseline.
    # Never substitute injected documents or generic read endpoints.
    try:
        refuse_unattested_context(None)
    except ValueError as exc:
        raise ApplicationError("sandbox_authorities_unavailable", non_retryable=True) from exc

def registered_activities(existing, *, enabled, namespace, address):
    if enabled not in ("0", "1"):
        raise ValueError("invalid_sandbox_registration_flag")
    if enabled == "0":
        return list(existing)
    if namespace != "acme-int06" or address != "aiops2-temporal:7233":
        raise ValueError("sandbox_registration_boundary")
    return [*existing, acme_no_effect_activity]
