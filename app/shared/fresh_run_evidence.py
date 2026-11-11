"""Fail-closed readback of a fresh Run's persisted Evidence and canonical digests.

Runs inside the disposable qualification network only; no writes or credentials in receipts.
A digest is not a cryptographic signature. DB row existence is verified through the
Evidence service readback, not a separate direct SQL connection.
"""
import re
from shared.evidence_identity import canonical_evidence, evidence_digest

def verify_run_evidence(run_id, completed_events, core_listing, fetch_evidence):
    if not isinstance(run_id,str) or not re.fullmatch(r"RUN-[A-Za-z0-9-]{6,80}",run_id):
        raise ValueError("INVALID_RUN_ID")
    if not isinstance(completed_events,list) or not completed_events:
        raise ValueError("NO_COMPLETED_EVENTS")
    if not isinstance(core_listing,dict) or core_listing.get("run_id")!=run_id:
        raise ValueError("CORE_EVIDENCE_RUN_MISMATCH")
    rows=core_listing.get("items")
    if not isinstance(rows,list) or core_listing.get("payload_excluded") is not True:
        raise ValueError("CORE_EVIDENCE_CONTRACT_MISMATCH")
    linked=set()
    for event in completed_events:
        ids=event.get("evidence_ids") if isinstance(event,dict) else None
        if not isinstance(ids,list) or not ids or any(not isinstance(i,str) or not i for i in ids):
            raise ValueError("STAGE_EVIDENCE_LINK_MISSING")
        linked.update(ids)
    if len(rows)!=len(linked) or {r.get("evidence_id") for r in rows if isinstance(r,dict)}!=linked:
        raise ValueError("CORE_EVIDENCE_READBACK_INCOMPLETE")
    verified=[]
    for eid in sorted(linked):
        record=fetch_evidence(eid)
        if not isinstance(record,dict) or record.get("evidence_id")!=eid:
            raise ValueError("EVIDENCE_READBACK_ID_MISMATCH")
        if not isinstance(record.get("provenance"),dict) or record["provenance"].get("run_id")!=run_id:
            raise ValueError("EVIDENCE_PROVENANCE_RUN_MISMATCH")
        if record["provenance"].get("synthetic") is not True:
            raise ValueError("EVIDENCE_NOT_SYNTHETIC")
        envelope=canonical_evidence(**{key:record[key] for key in (
            "source","external_id","observed_at","claim","confidence","provenance","payload")})
        if evidence_digest(envelope)!=record.get("payload_hash"):
            raise ValueError("EVIDENCE_DIGEST_MISMATCH")
        listing=next(r for r in rows if r["evidence_id"]==eid)
        if listing.get("payload_hash")!=record["payload_hash"]:
            raise ValueError("CORE_EVIDENCE_HASH_MISMATCH")
        verified.append(eid)
    return {"run_id":run_id,"verified_persisted_evidence":len(verified),
            "canonical_sha256_readback":"PASS","cryptographic_signature":"NOT_VERIFIED",
            "database_direct_sql":"NOT_VERIFIED","file_artifacts":"NOT_VERIFIED"}
