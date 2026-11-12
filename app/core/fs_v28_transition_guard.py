"""Pure, non-authoritative DEMO transition validation; never dispatches Temporal."""
from __future__ import annotations

STAGES = ("OBSERVE", "ANALYST", "CRITIC", "POLICY")


def validate(events: list[dict], *, incident_id: str, run_id: str, evidence_id: str) -> dict:
    """Reject gaps, conflicting retries and any post-denial progression fail-closed."""
    failed = {"status": "UNAVAILABLE", "reason": "INVALID_TRANSITION", "can_start": False,
              "can_resolve": False, "live_effects": False}
    if not isinstance(events, list) or not all(isinstance(e, dict) for e in events):
        return failed
    seen = {}
    step = 0
    terminal = False
    for event in events:
        if (event.get("incident_id") != incident_id or event.get("run_id") != run_id
                or event.get("evidence_id") != evidence_id or event.get("mode") != "DEMO"
                or event.get("live_effects") is not False):
            return failed
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            return failed
        if event_id in seen:
            if seen[event_id] != event:
                return failed
            continue
        if terminal:
            return failed
        stage = event.get("stage")
        if step >= len(STAGES) or stage != STAGES[step]:
            return failed
        if stage == "POLICY":
            if event.get("decision") not in ("DENY", "BLOCK", "BLOCKED"):
                return failed
            terminal = True
        elif "decision" in event:
            return failed
        seen[event_id] = dict(event)
        step += 1
    return {"status": "BLOCKED_NO_EFFECT" if terminal else ("CREATED" if step == 0 else "IN_PROGRESS"),
            "reason": "POLICY_REFUSED" if terminal else "NO_AUTHORITY_TO_ADVANCE",
            "can_start": False, "can_resolve": False, "live_effects": False}
