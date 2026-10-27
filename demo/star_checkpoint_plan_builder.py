"""Construct strict read-only STAR capture plans from independently supplied IDs.

No network, browser, credentials, ticket writes, run-ID generation, or LIVE action.
A plan is not evidence; downstream Chromium must check the exact DOM and masks.
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import quote, urlencode
import re

from demo.star_snapshot_browser import CapturePlan, validate_plan
from demo.star_snapshot_choreography import CUES

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,95}\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
_DIGITS = re.compile(r"[0-9]{1,18}\Z")
_PORTS = {"grafana": 3000, "n8n": 5678, "glpi": 8080}
_ENVIRONMENTS = {"ISOLATED_TEST_FIXTURE", "OPERATOR_BROWSER_UNREVIEWED"}


def _keys(mapping: object, required: set[str], label: str) -> Mapping:
    if not isinstance(mapping, Mapping) or set(mapping) != required:
        raise ValueError("missing or unexpected " + label)
    return mapping


def build_star_capture_plans(spec: Mapping[str, object]) -> tuple[CapturePlan, ...]:
    """Build nine ordered plans; refuse absent, contradictory or guessed IDs.

    Caller must independently obtain each event_ref from the application's
    execution/ticket/dashboard record. Repeated GLPI ticket IDs are allowed,
    but an n8n execution ID may not silently represent two checkpoints.
    No origin is contacted. No capture is approved by constructing a plan.
    """
    _keys(spec, {"run_id", "correlation_id", "environment", "origins", "checkpoints"}, "spec fields")
    run_id, correlation_id = spec["run_id"], spec["correlation_id"]
    if not isinstance(run_id, str) or not _ID.fullmatch(run_id):
        raise ValueError("missing canonical run_id")
    if not isinstance(correlation_id, str) or not _ID.fullmatch(correlation_id):
        raise ValueError("missing canonical correlation_id")
    if not isinstance(spec["environment"], str) or spec["environment"] not in _ENVIRONMENTS:
        raise ValueError("invalid environment")
    origins = _keys(spec["origins"], set(_PORTS), "application origins")
    from urllib.parse import urlsplit
    from demo.star_browser_request_fence import canonical_origin
    for app, origin in origins.items():
        if not isinstance(origin, str) or canonical_origin(origin) != origin:
            raise ValueError("noncanonical application origin")
        parts = urlsplit(origin)
        if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost"}
                or parts.port != _PORTS[app] or parts.path or parts.query or parts.fragment):
            raise ValueError("wrong legacy application port or origin")
    cues = {c.cue for c in CUES}
    checkpoints = _keys(spec["checkpoints"], cues, "STAR checkpoints")
    plans: list[CapturePlan] = []
    seen_executions: set[str] = set()
    for cue in CUES:
        item = _keys(checkpoints[cue.cue],
                     {"event_ref", "selectors", "route"}, "checkpoint fields")
        ref = item["event_ref"]
        if not isinstance(ref, str) or not _SEGMENT.fullmatch(ref):
            raise ValueError("missing or invalid application event_ref")
        selectors = _keys(item["selectors"],
                          {"run", "correlation", "event", "state", "redact"}, "DOM selectors")
        if not isinstance(selectors["redact"], (list, tuple)):
            raise ValueError("redaction selectors must be a sequence")
        redactions = tuple(selectors["redact"])
        route = item["route"]
        origin = origins[cue.service]
        if cue.service == "glpi":
            _keys(route, set(), "GLPI route")
            if not _DIGITS.fullmatch(ref):
                raise ValueError("GLPI ticket ID required")
            url = origin + "/front/ticket.form.php?" + urlencode({"id": ref})
        elif cue.service == "n8n":
            _keys(route, {"workflow_id"}, "n8n route")
            workflow = route["workflow_id"]
            if not isinstance(workflow, str) or not _SEGMENT.fullmatch(workflow):
                raise ValueError("missing n8n workflow ID")
            if not _DIGITS.fullmatch(ref) or ref in seen_executions:
                raise ValueError("n8n execution ID missing or reused")
            seen_executions.add(ref)
            url = origin + "/workflow/" + quote(workflow, safe="") + "/executions/" + quote(ref, safe="")
        else:
            _keys(route, {"slug", "from_ms", "to_ms"}, "Grafana route")
            slug, start, end = route["slug"], route["from_ms"], route["to_ms"]
            if not isinstance(slug, str) or not _SEGMENT.fullmatch(slug):
                raise ValueError("Grafana slug missing")
            if (type(start) is not int or type(end) is not int or
                    start < 1_000_000_000_000 or end <= start or end-start > 3_600_000):
                raise ValueError("Grafana fixed event window required")
            url = (origin + "/d/" + quote(ref, safe="") + "/" + quote(slug, safe="") + "?" +
                   urlencode({"from": str(start), "to": str(end), "var-run_id": run_id}))
        plan = CapturePlan(
            cue=cue.cue, run_id=run_id, correlation_id=correlation_id,
            event_ref=ref, url=url, expected_state=cue.required_state,
            identity_selector=selectors["run"], correlation_selector=selectors["correlation"],
            event_selector=selectors["event"], state_selector=selectors["state"],
            redact_selectors=redactions, allowed_origin=origin,
            environment=spec["environment"], approved_get_urls=(),
        )
        validate_plan(plan)
        plans.append(plan)
    return tuple(plans)
