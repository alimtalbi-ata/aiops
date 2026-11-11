"""Fail-closed command mapping for isolated simulation policy evaluation.

A DEMO/REPLAY/STORY decision is a read-only disposition request. The Policy
engine may return SIMULATE, but this module never authorizes any LIVE effect.
"""

import hmac


def valid_internal_bearer(authorization: object, expected_token: object) -> bool:
    """Require an exact Bearer scheme for the internal Worker start endpoint.

    Never accept a bare shared secret or a differently cased/ambiguous header.
    This authenticates only the internal caller, not a tenant or HITL actor.
    """
    return (type(authorization) is str and type(expected_token) is str
            and bool(expected_token) and authorization.startswith("Bearer ")
            and hmac.compare_digest(authorization.encode("utf-8"),
                                    ("Bearer " + expected_token).encode("utf-8")))


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


def validate_synthetic_gate_receipt(receipt: object, run_id: str, policy: dict) -> dict:
    """Require Core's gate write acknowledgement to match this synthetic Run.

    This is a transport acknowledgement, NOT proof of Policy provenance,
    Evidence linkage, tenant authorization, or an executed Temporal workflow.
    """
    if (not isinstance(run_id, str) or not run_id
            or not isinstance(policy, dict)
            or not isinstance(receipt, dict)
            or set(receipt) != {"run_id", "stage", "state"}
            or receipt.get("run_id") != run_id
            or receipt.get("stage") != "POLICY"
            or receipt.get("state") != policy.get("state")):
        raise ValueError("untrusted synthetic Core gate receipt")
    return receipt


def validate_canonical_run_binding(response: object, args: object, *, allow_started: bool = False) -> dict:
    """Bind a worker request to Core's canonical Run before any stage effect.

    This is a consistency check under the internal service token, NOT tenant
    RBAC, authenticated Policy provenance, or an atomic Core reservation.
    The Core START command still enforces its own expected_version.
    """
    if (not isinstance(args, dict)
            or any(type(args.get(k)) is not str or not args[k]
                   for k in ("run_id", "mode", "scenario_id"))
            or args["mode"] not in ("DEMO", "REPLAY", "STORY", "LIVE")
            or type(args.get("version")) is not int or args["version"] < 1
            or not isinstance(response, dict)
            or not isinstance(response.get("run"), dict)):
        raise ValueError("invalid canonical execution binding")
    run = response["run"]
    if (any(type(run.get(k)) is not str or run[k] != args[k]
            for k in ("run_id", "mode", "scenario_id"))
            or type(run.get("version")) is not int):
        raise ValueError("canonical execution identity mismatch")
    if allow_started:
        if run.get("status") not in ("CREATED", "RUNNING") or run["version"] < args["version"]:
            raise ValueError("canonical execution state mismatch")
    elif run.get("status") != "CREATED" or run["version"] != args["version"]:
        raise ValueError("canonical execution state mismatch")
    return run
