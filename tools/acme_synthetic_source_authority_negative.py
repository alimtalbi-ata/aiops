"""ACME seven-event negative source authority contract; offline and read-only.

Three SHA256 values are local projections, never Core PG16 payload/full-event
hashes or authenticated Incident/Run/GLPI/HITL receipts. No network or writes.
"""
import argparse
import hashlib
import json

from tools import acme_synthetic_three_domain_receipt as source
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.synthetic-seven-source-authority-negative.v1"
FIXTURE = (gen.ROOT / "docs/customer-story" /
           "ACME-SYNTHETIC-SEVEN-SOURCE-AUTHORITY-NEGATIVE-2026-11-01.json")
FIELDS = ("acme_full_event_sha256", "acme_local_payload_sha256",
          "proposed_core_payload_sha256")


def build_negative_receipt(manifest):
    """Derive a redacted negative fixture from the existing pinned source."""
    receipt = source.build_receipt(manifest)  # enforces pinned seed and graph
    if (receipt["source_event_count"] != 7 or
            receipt["core_manifest_status"] != "UNAVAILABLE" or
            receipt["hash_domains_equivalent"] is not False or
            receipt["core_runtime_source_hashes_verified"] is not False):
        raise ValueError("Core authority unexpectedly promoted")
    rows = []
    for sequence, (event, row) in enumerate(
            zip(manifest["events"], receipt["source_event_rows"]), 1):
        if (row["sequence"] != sequence or
                row["source_event_id"] != event["source_event_id"] or
                len({row[k] for k in FIELDS}) != 3 or
                row["acme_full_event_sha256"] !=
                hashlib.sha256(gen._canonical(event)).hexdigest() or
                row["acme_local_payload_sha256"] !=
                hashlib.sha256(gen._canonical(event["payload"])).hexdigest() or
                row["core_full_run_event_sha256"] is not None or
                row["core_event_id"] is not None or
                row["core_evidence_id"] is not None):
            raise ValueError("missing, reordered, foreign or forged event")
        rows.append({
            "sequence": sequence,
            "source_event_id": row["source_event_id"],
            **{k: row[k] for k in FIELDS},
            "core_pg16_payload_sha256": None,
            "core_pg16_full_event_sha256": None,
            "mapping_status": "UNAVAILABLE",
        })
    if len(rows) != 7 or len({r["source_event_id"] for r in rows}) != 7:
        raise ValueError("seven distinct source events required")
    if (len(receipt["itil_stages"]) != 15 or
            len(receipt["checkpoints"]) != 6 or
            any(s["status"] != "NOT_EXECUTED" for s in receipt["itil_stages"]) or
            any(c["status"] != "NOT_EXECUTED" or c["id"] is not None
                for c in receipt["checkpoints"])):
        raise ValueError("unexecuted ITIL projection required")
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "provenance": "SYNTHETIC_FIXTURE",
        "authority": "OFFLINE_ONLY",
        "result": "UNAVAILABLE",
        "seed": 20261018,
        "graph_version": receipt["graph_version"],
        "source_replay_sha256": receipt["source_replay_sha256"],
        "core_binding_schema": receipt["core_manifest_schema"],
        "core_receipt_schema": "aiops.core-canonical-seven-source-receipt.v1",
        "hash_domains": {
            "acme_full_event": "LOCAL_SHA256_CANONICAL_ACME_EVENT",
            "acme_local_payload": "LOCAL_SHA256_CANONICAL_ACME_PAYLOAD",
            "proposed_core_payload": "LOCAL_SHA256_SCHEMA_WRAPPED_PROJECTION",
            "core_pg16_payload": "UNKNOWN",
            "core_pg16_full_event": "UNKNOWN",
            "equivalence": "UNAVAILABLE",
        },
        "events": rows,
        "runtime_authority": {
            "actor_subject": None, "tenant_id": None,
            "incident_id": None, "run_id": None,
            "glpi_ticket_id": None, "evidence_ids": [],
            "hitl_approval": None, "freshness": "UNKNOWN",
            "revocation": "UNKNOWN", "observed_impact": "UNKNOWN",
            "core_pg16_readback": "UNAVAILABLE",
        },
        "itil_stages": {"count": 15, "status": "NOT_EXECUTED"},
        "checkpoints": {"count": 6, "status": "NOT_EXECUTED"},
        "runtime_readback": "NOT_EXECUTED",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
    }


def verify_negative_receipt(manifest, candidate):
    """Strict equality rejects foreign/missing/reordered source events.

    Passing offline check is still UNAVAILABLE; no Core readback is made.
    """
    expected = build_negative_receipt(manifest)
    if type(candidate) is not dict or gen._canonical(candidate) != gen._canonical(expected):
        raise ValueError("foreign, missing, reordered or forged source authority")
    return {"result": "UNAVAILABLE", "source_event_count": 7,
            "core_pg16_authority": "UNKNOWN", "runtime_readback": "NOT_EXECUTED",
            "itil_stages_not_executed": 15, "checkpoints_not_executed": 6}


def main():
    parser = argparse.ArgumentParser(description="Offline ACME source authority negative")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    if args.emit:
        print(json.dumps(build_negative_receipt(manifest), sort_keys=True,
                         indent=2, ensure_ascii=True))
    else:
        raw = FIXTURE.read_text(encoding="utf-8")
        candidate = json.loads(raw, object_pairs_hook=gen._unique_object)
        print(json.dumps(verify_negative_receipt(manifest, candidate), sort_keys=True))


if __name__ == "__main__":
    main()
