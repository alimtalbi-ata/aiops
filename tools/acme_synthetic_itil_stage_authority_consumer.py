"""Fail-closed ACME 15-stage ITIL replay consumer (offline, SYNTHETIC).

A local Core/GLPI/Evidence-shaped JSON document is NOT independently
authenticated transport, actor/tenant ACL, PG16, GLPI human rights, immutable
Evidence or HITL authority. No positive verification path exists in this
fixture-only consumer; a future Core-owned adapter must supply those proofs.
No network, writes, new stores, model execution or LIVE effects.
"""
import argparse
import copy
import json
from pathlib import Path

from tools import acme_synthetic_core_readback_unknown_gate as core
from tools import acme_synthetic_itil_replay_verifier as replay
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.itil-stage-authority-consumer.v1"
FIXTURE = (gen.ROOT / "docs/customer-story" /
           "ACME-SYNTHETIC-ITIL-STAGE-AUTHORITY-UNKNOWN-2026-11-01.json")
REQUIRED_INDEPENDENT_AUTHORITIES = (
    "CORE_PG16_ACTOR_TENANT_AUTHORIZED_SEVEN_EVENT_READBACK",
    "GLPI_NATIVE_HUMAN_TICKET_ENTITY_RIGHTS",
    "IMMUTABLE_EVIDENCE_TENANT_RUN_SOURCE_BINDING",
)


def build_receipt(manifest):
    """Pin all 15 planned stages, six checkpoints and seven local hash triples."""
    offline = replay.verify_itil_replay_offline(manifest)
    pinned = core.build_fixture(manifest)
    source_rows = pinned["events"]
    if (len(source_rows) != 7 or len(offline["stages"]) != 15 or
            len(offline["checkpoints"]) != 6 or
            offline["source_event_ids"] !=
            [row["source_event_id"] for row in source_rows]):
        raise ValueError("inconsistent pinned ACME source and ITIL replay")

    stages = []
    for stage in offline["stages"]:
        step = stage["source_step"]
        if type(step) is not int or not 1 <= step <= 7:
            raise ValueError("invalid ITIL source step")
        row = source_rows[step - 1]
        if (stage["source_event_id"] != row["source_event_id"] or
                stage["source_event_content_sha256"] !=
                row["acme_full_event_sha256"] or
                stage["status"] != "NOT_EXECUTED" or
                stage["runtime_id"] is not None or
                stage["runtime_evidence_ids"] != []):
            raise ValueError("ITIL stage has no pinned local source anchor")
        stages.append({
            "stage": stage["stage"],
            "source_step": step,
            "source_event_id": row["source_event_id"],
            "acme_full_event_sha256": row["acme_full_event_sha256"],
            "runtime_checkpoint": stage["runtime_checkpoint"],
            "status": "NOT_EXECUTED",
            "verification": "UNKNOWN",
            "runtime_id": None,
            "runtime_evidence_ids": [],
        })
    checkpoints = copy.deepcopy(offline["checkpoints"])
    if (len({s["stage"] for s in stages}) != 15 or
            len({c["stage"] for c in checkpoints}) != 6 or
            any(c["status"] != "NOT_EXECUTED" or c["id"] is not None
                for c in checkpoints)):
        raise ValueError("untrusted ITIL stage or checkpoint authority")

    return {
        "schema": SCHEMA,
        "synthetic": True,
        "provenance": "SYNTHETIC_FIXTURE_ONLY",
        "seed": 20261018,
        "graph_version": pinned["graph_version"],
        "source_replay_sha256": pinned["source_replay_sha256"],
        "source_event_count": 7,
        "source_events": [{
            "sequence": row["sequence"],
            "source_event_id": row["source_event_id"],
            "acme_full_event_sha256": row["acme_full_event_sha256"],
            "acme_local_payload_sha256": row["acme_local_payload_sha256"],
            "proposed_core_payload_sha256": row["proposed_core_payload_sha256"],
            "core_pg16_payload_sha256": None,
            "core_pg16_full_event_sha256": None,
        } for row in source_rows],
        "required_independent_authorities": list(REQUIRED_INDEPENDENT_AUTHORITIES),
        "authority": {
            "core_readback": "UNAVAILABLE",
            "core_shape_reason": "NO_INDEPENDENT_CORE_READBACK",
            "core_pg16_authority": "UNKNOWN",
            "glpi_readback": "UNAVAILABLE",
            "glpi_human_rights": "UNKNOWN",
            "evidence_readback": "UNAVAILABLE",
            "evidence_authority": "UNKNOWN",
            "actor_subject": None,
            "tenant_id": None,
            "incident_id": None,
            "run_id": None,
            "glpi_ticket_id": None,
            "evidence_ids": [],
            "hitl_approval": None,
            "hash_domain_equivalence": "UNKNOWN",
            "freshness": "UNKNOWN",
            "revocation": "UNKNOWN",
            "observed_impact": "UNKNOWN",
        },
        "stage_count": 15,
        "verified_stage_count": 0,
        "not_executed_stage_count": 15,
        "stages": stages,
        "checkpoint_count": 6,
        "verified_checkpoint_count": 0,
        "not_executed_checkpoint_count": 6,
        "checkpoints": checkpoints,
        "result": "UNKNOWN",
        "runtime_readback": "NOT_EXECUTED",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def verify_receipt(manifest, candidate):
    """Reject modified/missing/reordered stages and forged positive authority."""
    expected = build_receipt(manifest)
    if type(candidate) is not dict or gen._canonical(candidate) != gen._canonical(expected):
        raise ValueError("foreign, missing or promoted ITIL authority fixture")
    return expected


def consume(manifest, *, core_readback=None, glpi_receipt=None,
            evidence_receipt=None, candidate=None, now=None):
    """Assess untrusted supplied shapes; never turn them into runtime receipts.

    Even an apparently signed Core document or positive GLPI/Evidence flag
    cannot independently prove actor/tenant, 013/014 audit or revocation.
    """
    expected = build_receipt(manifest)
    if candidate is not None:
        verify_receipt(manifest, candidate)
    for supplied in (core_readback, glpi_receipt, evidence_receipt):
        if supplied is not None and type(supplied) is not dict:
            raise ValueError("untrusted non-object authority document")
    shape = core.assess_readback(manifest, core_readback, now=now)
    result = copy.deepcopy(expected)
    authority = result["authority"]
    authority["core_readback"] = shape["core_readback"]
    authority["core_shape_reason"] = shape["reason"]
    authority["glpi_readback"] = (
        "UNAVAILABLE" if glpi_receipt is None else "UNVERIFIED")
    authority["evidence_readback"] = (
        "UNAVAILABLE" if evidence_receipt is None else "UNVERIFIED")
    # Never copy caller-controlled IDs, claims, bearer tokens or signatures.
    # Only the owning services can verify these independent authorities.
    return result


def _read_untrusted(path):
    if path is None:
        return None
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("oversized authority document")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=gen._unique_object)


def main():
    parser = argparse.ArgumentParser(description="Offline ACME ITIL receipt consumer")
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--core-readback", type=Path)
    parser.add_argument("--glpi-receipt", type=Path)
    parser.add_argument("--evidence-receipt", type=Path)
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    if args.emit:
        if any((args.check, args.core_readback, args.glpi_receipt,
                args.evidence_receipt)):
            parser.error("--emit cannot consume authority documents")
        print(json.dumps(build_receipt(manifest), sort_keys=True, indent=2,
                         ensure_ascii=True))
        return
    fixture = _read_untrusted(FIXTURE)
    verify_receipt(manifest, fixture)
    print(json.dumps(consume(
        manifest, candidate=fixture,
        core_readback=_read_untrusted(args.core_readback),
        glpi_receipt=_read_untrusted(args.glpi_receipt),
        evidence_receipt=_read_untrusted(args.evidence_receipt)),
        sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()
