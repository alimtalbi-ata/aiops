"""ACME-only executable SAN->Payments Twin impact handoff (SYNTHETIC).

Provides a deterministic seven-event, one-*candidate*-incident read model and
Core-compatible TEST_ONLY payloads for a future Core-owned disposable PG16
producer. Neither a portable receipt nor matching bytes establish PG16 actor/
tenant authority, GLPI human rights, HITL approval or an executed ITIL stage.
No database, HTTP, host, GLPI or LIVE side effects.
"""
import argparse
import hashlib
import json
from pathlib import Path

from tools import acme_synthetic_pg16_independent_intake as intake
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.twin-impact-core-handoff.v1"
CORE_PAYLOAD_DOMAIN = "aiops.core-source-event-payload.v1"
FIXTURE = (gen.ROOT / "docs/customer-story" /
           "ACME-TWIN-CORE-HANDOFF-UNKNOWN-2026-11-01.json")
TEST_SCOPE_KEYS = frozenset((
    "tenant_id", "incident_id", "run_id", "ticket_id", "glpi_entity_id",
))


def disposable_core_payloads(manifest, scope):
    """Prepare Core-domain payloads; Core owns INSERT, readback and authority.

    All identifiers must be explicitly supplied TEST_ONLY values. No runtime
    identifiers are derived from source-event IDs, titles or correlation keys.
    A proposed payload hash is NOT a persisted Core PG16 full/payload hash.
    """
    impact = gen.event_impact_contract_offline(manifest)
    if (type(scope) is not dict or set(scope) != TEST_SCOPE_KEYS
            or any(type(value) is not str
                   or not value.startswith("TEST_ONLY_")
                   or not 10 <= len(value) <= 96
                   for value in scope.values())
            or len(set(scope.values())) != len(TEST_SCOPE_KEYS)):
        raise ValueError("explicit distinct disposable TEST_ONLY Core scope required")
    rows = []
    for sequence, event in enumerate(impact["timeline"], 1):
        if event["step"] != sequence:
            raise ValueError("noncanonical ACME source event order")
        payload = {
            "source_event_id": event["source_event_id"],
            "sequence": sequence,
            "tenant_id": scope["tenant_id"],
            "incident_id": scope["incident_id"],
            "run_id": scope["run_id"],
            "ticket_id": scope["ticket_id"],
            "glpi_entity_id": scope["glpi_entity_id"],
            "ci_id": event["ci_id"],
            "action": event["action"],
            "source_event_time": event["event_time"],
            "synthetic": True,
        }
        rows.append({
            "sequence": sequence,
            "source_event_id": event["source_event_id"],
            "payload": payload,
            "proposed_core_payload_sha256": hashlib.sha256(
                gen._canonical({"schema": CORE_PAYLOAD_DOMAIN, "event": payload})
            ).hexdigest(),
            "core_pg16_full_event_sha256": None,
            "core_pg16_payload_sha256": None,
            "authority": "TEST_ONLY_PROPOSAL_NOT_PG16",
        })
    if len(rows) != 7 or len({r["source_event_id"] for r in rows}) != 7:
        raise ValueError("missing or duplicate ACME source event")
    return rows


def build_preview(manifest, *, core_readback=None, audit_proofs=None,
                  expected_tenant=None, expected_actor_sha256=None, now=None):
    """Expose a safe, deterministic API-neutral Portal preview, never runtime."""
    impact = gen.event_impact_contract_offline(manifest)
    local = intake.consume(
        manifest, core_readback=core_readback, audit_proofs=audit_proofs,
        expected_tenant=expected_tenant,
        expected_actor_sha256=expected_actor_sha256, now=now)
    events = []
    for i, (source, digest) in enumerate(
            zip(impact["timeline"], local["events"]), 1):
        if (source["step"] != i or digest["sequence"] != i
                or source["source_event_id"] != digest["source_event_id"]):
            raise ValueError("Core/ACME source sequence mismatch")
        events.append({
            "sequence": i,
            "source_event_id": source["source_event_id"],
            "event_time": source["event_time"],
            "ci_id": source["ci_id"],
            "action": source["action"],
            "acme_full_event_sha256": digest["acme_full_event_sha256"],
            "acme_local_payload_sha256": digest["acme_local_payload_sha256"],
            "proposed_core_payload_sha256": digest["proposed_core_payload_sha256"],
            "core_pg16_full_event_sha256": None,
            "core_pg16_payload_sha256": None,
        })
    if (len(events) != 7 or len({r["source_event_id"] for r in events}) != 7
            or local["verified_stage_count"] != 0
            or local["verified_checkpoint_count"] != 0):
        raise ValueError("noncanonical or promoted ACME read model")
    blast = impact["blast_radius_candidate"]
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "provenance": "SYNTHETIC_FIXTURE_ONLY",
        "portal_read_model_kind": "SYNTHETIC_PREVIEW_ONLY",
        "portal_integration_status": "NOT_CONNECTED",
        "seed": manifest["seed"],
        "scenario_id": impact["scenario_id"],
        "graph_version": impact["graph_version"],
        "source_replay_sha256": local["source_replay_sha256"],
        "source_event_count": 7,
        "events": events,
        "correlation": {
            "key": impact["correlation"]["key"],
            "scope": "LOCAL_FIXTURE_ONLY",
            "event_count": 7,
        },
        "candidate_incident": {
            "candidate_count": 1,
            "id": None,
            "status": "NOT_CREATED",
            "correlation_key": impact["correlation"]["key"],
            "canonical_core_authority": "UNKNOWN",
        },
        "twin_impact": {
            "source_ci_id": blast["source_ci_id"],
            "selected_service_id": blast["selected_service_id"],
            "path_node_ids": blast["path_node_ids"],
            "path_edge_ids": blast["path_edge_ids"],
            "candidate_service_ids": blast["candidate_service_ids"],
            "candidate_ci_count": blast["candidate_ci_count"],
            "estimated_impact_level": blast["estimated_impact_level"],
            "observed_service_impact": "UNKNOWN",
            "causality_verified": False,
            "redundancy_evaluated": False,
            "source_git_blob": impact["graph_version"],
        },
        "itil_priority_candidate": impact["itil"]["priority_candidate"],
        "itil_priority_confirmed": "UNKNOWN",
        "core_readback_status": local["readback_status"],
        "core_readback_reason": local["readback_reason"],
        "core_pg16_full_payload_equivalence": "UNKNOWN",
        "actor_tenant_acl": "UNKNOWN",
        "audit_013_014": "UNKNOWN",
        "freshness": "UNKNOWN",
        "revocation": "UNKNOWN",
        "runtime": {
            "tenant_id": None, "actor_subject": None,
            "incident_id": None, "run_id": None, "glpi_ticket_id": None,
            "evidence_ids": [], "hitl_approval": None,
        },
        "itil_stages": {
            "count": 15, "verified": 0, "not_executed": 15,
            "status": "NOT_EXECUTED",
        },
        "checkpoints": {
            "count": 6, "verified": 0, "not_executed": 6,
            "status": "NOT_EXECUTED",
        },
        "result": "UNKNOWN",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description="ACME synthetic Twin impact handoff")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--emit", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--core-readback", type=Path)
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    if args.check:
        pinned = intake._read_untrusted(FIXTURE)
        if gen._canonical(pinned) != gen._canonical(build_preview(manifest)):
            raise ValueError("modified ACME Twin impact handoff fixture")
    supplied = (intake._read_untrusted(args.core_readback)
                if args.core_readback else None)
    result = build_preview(manifest, core_readback=supplied)
    if args.check:
        print(json.dumps({
            "check": "PASS_SYNTHETIC_ONLY",
            "source_event_count": result["source_event_count"],
            "candidate_incident_count": result["candidate_incident"]["candidate_count"],
            "verified_stage_count": 0,
            "verified_checkpoint_count": 0,
            "core_pg16_authority": "UNKNOWN",
        }, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
