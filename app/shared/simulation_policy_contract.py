"""Fail-closed command mapping for isolated simulation policy evaluation.

A DEMO/REPLAY/STORY decision is a read-only disposition request. The Policy
engine may return SIMULATE, but this module never authorizes any LIVE effect.
"""


def policy_command_for_mode(mode: str) -> str:
    if mode == "LIVE":
        return "EXECUTE"  # still blocked by LIVE emergency stop / HITL / fencing
    if mode in ("DEMO", "REPLAY", "STORY"):
        return "OBSERVE"  # bypasses effect-only preconditions, NOT evidence/critic checks
    raise ValueError("unrecognized execution mode")
