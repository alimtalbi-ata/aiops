#!/usr/bin/env python3
"""Deterministic, fail-closed reducer for a verified coordination event stream.

Pure functions; does not dispatch Codex or mutate GitHub/Debian.
"""
from collections import defaultdict
from validate_message import validate, InvalidMessage, utc

INITIAL = "PROPOSED"
TRANSITIONS = {
    "PROPOSED": {"TASK_REQUEST": "READY"},
    "READY": {"TASK_ACCEPTED": "RUNNING", "TASK_CANCELLED": "CANCELLED"},
    "RUNNING": {"HEARTBEAT": "RUNNING", "BLOCKED": "BLOCKED",
                "ARTIFACT_READY": "ARTIFACT_READY", "TASK_FAILED": "FAILED",
                "APPROVAL_REQUIRED": "WAITING_APPROVAL"},
    "BLOCKED": {"TASK_REQUEST": "READY", "TASK_CANCELLED": "CANCELLED"},
    "WAITING_APPROVAL": {"TASK_REQUEST": "READY", "TASK_CANCELLED": "CANCELLED"},
    "ARTIFACT_READY": {"TEST_RESULT": "VERIFIED", "TASK_FAILED": "FAILED"},
    "VERIFIED": {"DEPLOY_CANDIDATE": "INTEGRATED", "TASK_FAILED": "FAILED"},
    "INTEGRATED": {"RUNTIME_RECEIPT": "INTEGRATED", "E2E_RESULT": "DEMONSTRATED",
                   "TASK_FAILED": "FAILED"},
    "DEMONSTRATED": {"TASK_DONE": "DONE"},
}
TERMINAL = frozenset(("DONE", "FAILED", "CANCELLED"))

def reduce_messages(messages):
    """Return per-work state. Reject contradictory, duplicate and unproven transitions."""
    states = {}
    seen_ids = set()
    seen_keys = set()
    last_times = {}
    for message in messages:
        validate(message)
        mid, key, work = message["message_id"], message["idempotency_key"], message["work_id"]
        if mid in seen_ids or key in seen_keys:
            raise InvalidMessage("duplicate message_id or idempotency_key")
        seen_ids.add(mid)
        seen_keys.add(key)
        when = utc(message["created_at"])
        if work in last_times and when < last_times[work]:
            raise InvalidMessage("out-of-order work event")
        last_times[work] = when
        previous = states.get(work, INITIAL)
        kind = message["kind"]
        if kind not in TRANSITIONS.get(previous, {}):
            raise InvalidMessage(f"invalid transition {previous} + {kind}")
        if kind in ("TASK_ACCEPTED", "ARTIFACT_READY", "TEST_RESULT", "RUNTIME_RECEIPT", "E2E_RESULT", "TASK_DONE"):
            if not message["evidence_refs"]:
                raise InvalidMessage(f"{kind} requires evidence")
        if kind == "TASK_ACCEPTED" and not message["producer"].startswith("codex."):
            raise InvalidMessage("only Codex executor may acknowledge a task")
        if kind in ("TEST_RESULT", "RUNTIME_RECEIPT", "E2E_RESULT") and message["producer"] not in ("github.actions", "debian.reporter", "codex.integration", "codex.debian"):
            raise InvalidMessage("untrusted verification producer")
        states[work] = TRANSITIONS[previous][kind]
    return states
