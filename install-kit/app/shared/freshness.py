"""Deterministic evidence freshness policy shared by analysis and policy callers."""
from __future__ import annotations
from datetime import datetime, timezone
import os

DEFAULT_MAX_AGE_SECONDS = 900
FUTURE_CLOCK_SKEW_SECONDS = 300

def _parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    raw=value.strip()
    if raw.endswith("Z"):
        raw=raw[:-1]+"+00:00"
    try:
        parsed=datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)

def assess_evidence_freshness(evidence, now=None, max_age_seconds=None):
    """Return a conservative aggregate; missing/ambiguous time is never treated as fresh."""
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if max_age_seconds is None:
        try:
            max_age_seconds=max(1,int(os.getenv("AIOPS_EVIDENCE_MAX_AGE_SECONDS",str(DEFAULT_MAX_AGE_SECONDS))))
        except (TypeError,ValueError):
            max_age_seconds=DEFAULT_MAX_AGE_SECONDS
    items=[]
    for item in evidence or []:
        provenance=item.get("provenance") if isinstance(item.get("provenance"),dict) else {}
        observed=item.get("observed_at") or provenance.get("observed_at")
        parsed=_parse_timestamp(observed)
        age=None if parsed is None else round((now-parsed).total_seconds(),3)
        if parsed is None:
            status="UNKNOWN"; reason="observed_at_missing_or_timezone_ambiguous"
        elif age < -FUTURE_CLOCK_SKEW_SECONDS:
            status="FUTURE"; reason="observed_at_exceeds_allowed_clock_skew"
        elif age > max_age_seconds:
            status="STALE"; reason="observation_exceeds_maximum_age"
        else:
            status="FRESH"; reason="observation_within_maximum_age"
        items.append({"evidence_id":item.get("evidence_id"),"observed_at":observed,"age_seconds":age,"status":status,"reason":reason})
    statuses=[x["status"] for x in items]
    if not statuses or "UNKNOWN" in statuses:
        aggregate="UNKNOWN"
    elif "STALE" in statuses or "FUTURE" in statuses:
        aggregate="STALE"
    else:
        aggregate="FRESH"
    return {"status":aggregate,"max_age_seconds":max_age_seconds,"evidence_count":len(items),"fresh_count":statuses.count("FRESH"),"stale_count":statuses.count("STALE"),"future_count":statuses.count("FUTURE"),"unknown_count":statuses.count("UNKNOWN"),"items":items}

def annotate_evidence_freshness(evidence, now=None, max_age_seconds=None):
    """Copy evidence and attach deterministic freshness metadata for the model to inspect."""
    result=[]
    for item in evidence or []:
        copied=dict(item)
        result.append(copied)
    summary=assess_evidence_freshness(result,now=now,max_age_seconds=max_age_seconds)
    by_id={item.get("evidence_id"):item for item in summary["items"]}
    for item in result:
        item["_aiops_quality"]=by_id.get(item.get("evidence_id"),{"status":"UNKNOWN","reason":"evidence_id_missing"})
    return result,summary
