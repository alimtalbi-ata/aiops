"""FS147 read-only diagnostic orchestration; no remediation or ticket writes.

Adapters are supplied by the authenticated host application. This module does not
grant access: each adapter MUST enforce tenant/actor ACL and use its own credentials.
"""
from dataclasses import dataclass
from typing import Callable, Mapping
import hashlib
import json
import math
from datetime import datetime, timezone, timedelta


@dataclass(frozen=True)
class FS147Request:
    tenant_id: str
    actor_id: str
    incident_id: str
    run_id: str
    ticket_id: int = 147
    mode: str = "DEMO"


def _blocked(reason, steps=()):
    return {"status": "BLOCKED", "effect": "NO_EFFECT", "reason": reason,
            "steps": list(steps), "resolved": False}


def _matching(value, request):
    return (isinstance(value, Mapping)
            and value.get("tenant_id") == request.tenant_id
            and value.get("incident_id") == request.incident_id
            and value.get("run_id") == request.run_id
            and type(value.get("ticket_id")) is int
            and value["ticket_id"] == request.ticket_id
            and value.get("actor_id") == request.actor_id)


def _valid_observation_time(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError, TypeError, OverflowError):
        return False


def execute(request: FS147Request, *, stop_auto: bool,
            observe: Callable, analyst: Callable, critic: Callable,
            policy: Callable, claim_once: Callable, now: Callable = lambda: datetime.now(timezone.utc)):
    """Run only after authenticated Core has allocated a durable run.

    claim_once must be atomic and durable, scoped to tenant/incident/run/ticket.
    Each callback must be a real, authenticated service call; no mock fallback.
    No callback may perform a mutation of the lab or a GLPI ticket.
    """
    if stop_auto:
        return _blocked("STOP_AUTO")
    if (request.mode != "DEMO" or type(request.ticket_id) is not int or request.ticket_id != 147
            or any(type(identifier) is not str or not identifier.strip()
                   for identifier in (request.tenant_id, request.actor_id,
                                      request.incident_id, request.run_id))):
        return _blocked("INVALID_SCOPE")
    key = hashlib.sha256(json.dumps(
        [request.tenant_id, request.incident_id, request.run_id,
         request.ticket_id], separators=(",", ":")).encode()).hexdigest()
    try:
        claim_result = claim_once(key)
        if claim_result is False:
            return _blocked("DUPLICATE_RUN")
        if claim_result is not True:
            # Missing/ambiguous Core acknowledgement is not a proven duplicate.
            return _blocked("IDEMPOTENCY_UNAVAILABLE")
    except Exception:
        return _blocked("IDEMPOTENCY_UNAVAILABLE")
    steps = []
    try:
        observation = observe(request)
        if not _matching(observation, request):
            return _blocked("OBSERVATION_SCOPE", steps)
        if (observation.get("source") != "fs-lab-bridge-readonly"
                or observation.get("commands") != ["df", "du", "ls"]
                or not isinstance(observation.get("evidence_id"), str)
                or not observation["evidence_id"].strip()
                or not _valid_observation_time(observation.get("collected_at"))
                or type(observation.get("used_percent")) not in (int, float)
                or not math.isfinite(observation["used_percent"])
                or not 0 <= observation["used_percent"] <= 100
                or observation.get("filesystem") != "/fs-lab"
                or not observation.get("read_only") is True):
            return _blocked("INSUFFICIENT_OBSERVATION", steps)
        # A historical lab measurement is not proof of a fresh bridge observation.
        # Clock injection is only for deterministic tests, never a substitute for
        # an authenticated bridge response.
        observed_at = datetime.fromisoformat(
            observation["collected_at"].replace("Z", "+00:00"))
        age = now() - observed_at
        if not timedelta(seconds=-30) <= age <= timedelta(minutes=5):
            return _blocked("STALE_OBSERVATION", steps)
        steps.append("OBSERVE")
        analysis = analyst(request, observation)
        if not _matching(analysis, request) or analysis.get("evidence_id") != observation["evidence_id"]:
            return _blocked("ANALYST_SCOPE", steps)
        if (not isinstance(analysis.get("findings"), list)
                or not analysis["findings"]
                or any(not isinstance(item, str) or not item.strip()
                       for item in analysis["findings"])):
            return _blocked("INSUFFICIENT_ANALYSIS", steps)
        steps.append("ANALYST")
        critique = critic(request, observation, analysis)
        if not _matching(critique, request) or critique.get("evidence_id") != observation["evidence_id"]:
            return _blocked("CRITIC_SCOPE", steps)
        if critique.get("state") != "PASS":
            return _blocked("CRITIC_REFUSED", steps)
        steps.append("CRITIC")
        decision = policy(request, observation, analysis, critique)
        if not _matching(decision, request) or decision.get("evidence_id") != observation["evidence_id"]:
            return _blocked("POLICY_SCOPE", steps)
        steps.append("POLICY")
        if decision.get("state") != "PASS" or decision.get("decision") != "SIMULATE":
            return _blocked("POLICY_REFUSED", steps)
        return {"status": "NO_EFFECT", "effect": "NO_EFFECT", "resolved": False,
                "steps": steps, "run_id": request.run_id,
                "ticket_id": request.ticket_id, "evidence_id": observation["evidence_id"]}
    except TimeoutError:
        # A timeout is an indeterminate remote outcome, not proof of failure.
        # The durable Core claim remains consumed: never replay with a new claim.
        return _blocked("UNKNOWN_TIMEOUT", steps)
    except Exception:
        return _blocked("SERVICE_UNAVAILABLE", steps)
