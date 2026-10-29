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


def validate_synthetic_policy_response(response: object) -> dict:
    """Validate the Policy HTTP disposition before persisting a synthetic gate.

    A caller-controlled PASS/ALLOW, malformed body or unknown status must
    never become a Core PASS gate. This validates only the response shape,
    NOT its origin, critic/evidence provenance or a HITL receipt.
    """
    if not isinstance(response, dict) or set(response) != {"state", "decision", "reason"}:
        raise ValueError("untrusted synthetic Policy response")
    state, decision, reason = response["state"], response["decision"], response["reason"]
    if not all(isinstance(value, str) for value in (state, decision, reason)):
        raise ValueError("untrusted synthetic Policy response")
    if (state, decision) not in {
        ("PASS", "SIMULATE"),
        ("BLOCKED", "HUMAN_APPROVAL"),
        ("UNKNOWN", "HUMAN_APPROVAL"),
    } or not reason.strip():
        raise ValueError("untrusted synthetic Policy disposition")
    return response
