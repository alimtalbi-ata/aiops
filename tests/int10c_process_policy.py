"""Test-only process supervision policy; no subprocess or service creation."""
import asyncio

async def stop_owned(handle, *, expected_identity, timeout):
    if type(expected_identity) is not str or not expected_identity:
        raise ValueError("identity")
    if type(timeout) is not int or not 1 <= timeout <= 30:
        raise ValueError("timeout")
    try:
        if await asyncio.wait_for(handle.identity(),timeout) != expected_identity:
            return "IDENTITY_MISMATCH"
        await asyncio.wait_for(handle.terminate(),timeout)
        if await asyncio.wait_for(handle.absent(),timeout) is True:
            return "ABSENCE_REPORTED"
        if await asyncio.wait_for(handle.identity(),timeout) != expected_identity:
            return "IDENTITY_MISMATCH"
        await asyncio.wait_for(handle.kill(),timeout)
        if await asyncio.wait_for(handle.absent(),timeout) is True:
            return "ABSENCE_REPORTED"
    except Exception:
        pass
    return "NOT_QUALIFIED"
