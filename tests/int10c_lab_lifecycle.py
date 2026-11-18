"""Test-only lifecycle rehearsal with injected callbacks, not a service runner."""
import asyncio

async def rehearse(plan_result, *, exercise, cleanup, verify_absence, timeout):
    if plan_result != {"status":"PLAN_ONLY","launch_authorized":False,
                       "runtime_attested":False,"ownership":"UNKNOWN"}:
        raise ValueError("preflight_required")
    if type(timeout) is not int or not 1 <= timeout <= 900:
        raise ValueError("timeout")
    outcome = "COMPLETED"
    try:
        await asyncio.wait_for(exercise(), timeout)
    except TimeoutError:
        outcome = "TIMEOUT"
    except Exception:
        outcome = "INTERRUPTED"
    finally:
        cleaned = False
        try:
            await asyncio.wait_for(cleanup(), timeout)
            cleaned = await asyncio.wait_for(verify_absence(), timeout) is True
        except Exception:
            cleaned = False
    return {"status":"REHEARSAL_ONLY","outcome":outcome,
            "cleanup_observed":cleaned,"launch_authorized":False,
            "runtime_attested":False}
