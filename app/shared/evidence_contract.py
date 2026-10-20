"""Deterministic evidence integrity and diagnostic-quality guards.

No model output may grant trust to an observation. LIVE/DEMO history may be
useful context, but current-state claims require fresh, traceable records.
"""
from __future__ import annotations

from .freshness import assess_evidence_freshness


def validate_evidence(evidence):
    """Return reason codes for malformed or self-contradictory evidence input."""
    errors=[]
    seen=set()
    for position,item in enumerate(evidence):
        if not isinstance(item,dict):
            errors.append("evidence_not_an_object:"+str(position))
            continue
        eid=item.get("evidence_id")
        if not isinstance(eid,str) or not eid.strip() or len(eid)>200:
            errors.append("invalid_evidence_id:"+str(position))
        elif eid in seen:
            errors.append("duplicate_evidence_id:"+eid)
        else:
            seen.add(eid)
        provenance=item.get("provenance") or {}
        if not isinstance(provenance,dict):
            errors.append("invalid_provenance:"+str(position))
            continue
        top=item.get("observed_at")
        inherited=provenance.get("observed_at")
        if top and inherited and str(top)!=str(inherited):
            errors.append("conflicting_observed_at:"+str(position))
        if item.get("_aiops_quality") is not None:
            # Metadata is calculated internally; a client must not masquerade as the guard.
            errors.append("client_supplied_quality_metadata:"+str(position))
    return errors


def _fresh_ids(evidence):
    summary=assess_evidence_freshness(evidence)
    ids={item["evidence_id"] for item in summary["items"]
         if item["status"]=="FRESH" and isinstance(item.get("evidence_id"),str)}
    return ids,summary


def analysis_quality_errors(analysis,evidence):
    """Check that current critical claims have at least one *fresh* source."""
    fresh,summary=_fresh_ids(evidence)
    errors=[]
    hypotheses=analysis.get("hypotheses",[])
    if not isinstance(hypotheses,list) or not hypotheses:
        errors.append("missing_hypotheses")
        return errors
    cited=set()
    for h in hypotheses:
        cited.update(h.get("supporting_evidence_ids",[]))
        overlap=set(h.get("supporting_evidence_ids",[])) & set(h.get("contradicting_evidence_ids",[]))
        if overlap:
            errors.append("hypothesis_cites_same_evidence_as_support_and_contradiction")
    severity=analysis.get("severity","UNKNOWN")
    if severity in ("P1","P2","P3","P4") and not (cited & fresh):
        errors.append("current_severity_not_grounded_in_fresh_evidence")
    if severity=="UNKNOWN" and float(analysis.get("confidence",0))>0.65 and not fresh:
        errors.append("unknown_severity_overconfident_without_fresh_evidence")
    if summary["evidence_count"]==0:
        errors.append("evidence_is_empty")
    return errors


def contradictory_snapshots(evidence):
    """Detect diverging path/service snapshot states, including historical vs current.

    Does not conclude which source is true. Both must be exposed for Critic review.
    """
    snapshots=[]
    for item in evidence:
        payload=item.get("payload") if isinstance(item,dict) else None
        if not isinstance(payload,dict):
            continue
        if "active_paths" not in payload or "total_paths" not in payload:
            continue
        try:
            active=int(payload["active_paths"])
            total=int(payload["total_paths"])
        except (TypeError,ValueError):
            continue
        if total<=0 or not 0<=active<=total:
            continue
        snapshots.append((item.get("evidence_id"),active,total))
    if len(snapshots)<2:
        return []
    tensions=[]
    for index,left in enumerate(snapshots):
        for right in snapshots[index+1:]:
            if left[2]==right[2] and left[1]!=right[1]:
                tensions.append({"evidence_ids":[left[0],right[0]],"code":"DIVERGENT_PATH_SNAPSHOTS"})
    return tensions


def critique_quality_errors(critique,analysis,evidence):
    """Post-model independent checks before ever accepting 'validated=true'."""
    errors=[]
    checks=critique.get("claim_checks",[])
    if not checks or not all(c.get("supported") is True for c in checks):
        errors.append("incomplete_or_unsupported_claim_checks")
    known={item.get("evidence_id") for item in evidence if isinstance(item,dict)}
    fresh,summary=_fresh_ids(evidence)
    critical=analysis.get("severity") in ("P1","P2","P3","P4")
    if critical and not fresh:
        errors.append("no_fresh_evidence_for_current_claims")
    for check in checks:
        refs=set(check.get("supporting_evidence_ids",[]))
        if not refs.issubset(known):
            errors.append("critic_references_unknown_evidence")
        if check.get("supported") and critical and not (refs & fresh):
            errors.append("validated_current_claim_supported_only_by_stale_evidence")
    if contradictory_snapshots(evidence) and not critique.get("issues") and not analysis.get("contradictions"):
        errors.append("divergent_snapshots_not_challenged")
    if summary["unknown_count"] and not fresh and critique.get("validated"):
        errors.append("unknown_evidence_age_unacknowledged")
    return sorted(set(errors))
