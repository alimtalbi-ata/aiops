"""ACME-only graph-005 consumer of a Core-owned disposable PG16 CI receipt.

The input is the redacted artifact of a real Core-written PG16/TLS test, NOT
an independently authenticated runtime HTTPS response. A matching fixture
hash or a GitHub artifact digest cannot prove actor IdP/GLPI rights, audit
immutability, freshness or human approval. Never promote ITIL stage state.
No HTTP/SQL, host, GLPI, executor, or LIVE effects.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from tools import acme_synthetic_pg16_seven_bridge as bridge
from tools import acme_synthetic_itil_stage_authority_consumer as itil
from tools import acme_synthetic_https_seven_concordance as concordance
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.graph005-core-pg16-ci-consumer.v1"
CORE_SCHEMA = "aiops.core-graph005-seven-015-source-receipt.v1"
CORE_DOMAINS = {
    "full_event": "aiops.core-full-run-event.v1",
    "payload": "aiops.core-source-event-payload.v1",
}
CORE_ARTIFACT_URL = (
    "https://github.com/alimtalbi-ata/aiops/actions/runs/41382867559/"
    "artifacts/13114440885"
)
CORE_CI_HEAD = "3d4880256d5ffce0a403565ea12dffef2b0bf8e7"
CORE_CI_RECEIPT_SHA256 = "ceceff9e71ca414f2e5b0d9272408c10a3df7c2e405609d174036d419f989de2"
CORE_CI_FILE_SHA256 = "bf74927d5cfb847f86b4933ff21d3ebb13684a23335e362b1f3e88923a7c9617"
REQUIRED_NEGATIVES = frozenset((
    "expired", "foreign_actor", "foreign_incident", "foreign_run",
    "foreign_tenant", "foreign_ticket", "revoked",
))
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
EVENT_ID = re.compile(r"SYN-EVT-[0-9A-F]{20}\Z")
CORE_ROW_KEYS = frozenset((
    "source_event_id", "acme_fixture_full_sha256",
    "acme_fixture_payload_sha256", "core_pg16_full_event_sha256",
    "core_pg16_payload_sha256",
))


def _sha256(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _read_untrusted(path, *, expected_file_sha256):
    if type(expected_file_sha256) is not str or not HEX64.fullmatch(expected_file_sha256):
        raise ValueError("pinned Core CI file digest required")
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != expected_file_sha256:
        raise ValueError("Core CI receipt too large or file digest mismatch")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=gen._unique_object)


def _validate(core, local, graph_version, expected_head, expected_receipt_sha256):
    if (type(expected_head) is not str or not HEX40.fullmatch(expected_head)
            or type(expected_receipt_sha256) is not str
            or not HEX64.fullmatch(expected_receipt_sha256)):
        return "UNPINNED_CORE_CI_PROVENANCE"
    if type(core) is not dict or core.get("schema") != CORE_SCHEMA:
        return "MISSING_OR_FOREIGN_CORE_CI_RECEIPT"
    if (core.get("source_head") != expected_head
            or core.get("receipt_sha256") != expected_receipt_sha256
            or _sha256({k: v for k, v in core.items() if k != "receipt_sha256"})
            != expected_receipt_sha256):
        return "CORE_CI_HEAD_OR_RECEIPT_DIGEST_MISMATCH"
    if (core.get("graph_version") != graph_version
            or core.get("hash_domains") != CORE_DOMAINS
            or core.get("producer") !=
            "core.canonical_seven_pg_source.read_graph005_core_written_seven"
            or core.get("writer") != "core.main.app /api/runs/{rid}/events"
            or core.get("transport") != "DISPOSABLE_TLS_BASIC_BOUND"
            or core.get("source_fixture_only") is not True
            or core.get("actor_issuer_distinct_from_source") is not True):
        return "FOREIGN_GRAPH_SOURCE_OR_HASH_DOMAIN"
    if (core.get("portable_signature") != "NONE"
            or core.get("decision") != "UNKNOWN"
            or core.get("link_status") != "UNKNOWN"
            or core.get("human_glpi_attested") is not False
            or core.get("acme_full_event_equivalence") != "NOT_VERIFIED"
            or core.get("release_stable") != "NO_GO"):
        return "UNSUPPORTED_POSITIVE_CORE_AUTHORITY_CLAIM"
    if (core.get("installed") != ["001", "004", "009", "010", "011",
                                   "012", "013", "014", "015"]
            or core.get("native_pg16_restore") is not True
            or core.get("archive_retained") is not False
            or core.get("audit_before") != core.get("audit_after")
            or type(core.get("audit_before")) is not dict
            or any(type(v) is not int or v < 1
                   for v in core["audit_before"].values())
            or set(core["audit_before"]) !=
            {"nonce_013", "revocation_013", "terminal_014"}):
        return "CORE_CI_AUDIT_OR_RECOVERY_NOT_REPORTED"
    if (type(core.get("negative_cases")) is not dict
            or set(core["negative_cases"]) != REQUIRED_NEGATIVES
            or any(v != "UNKNOWN" for v in core["negative_cases"].values())
            or core.get("stale") != "UNKNOWN"
            or core.get("hash_mismatch") != "UNKNOWN"):
        return "CORE_CI_NEGATIVE_FENCES_NOT_REPORTED"
    if (any(type(core.get(k)) is not str or not core[k]
            for k in ("tenant_id", "incident_id", "run_id"))
            or len({core["tenant_id"], core["incident_id"], core["run_id"]}) != 3
            or type(core.get("actor_subject_sha256")) is not str
            or not HEX64.fullmatch(core["actor_subject_sha256"])):
        return "MISSING_DISPOSABLE_ACTOR_TENANT_INCIDENT_RUN_CLAIM"
    rows = core.get("events")
    if type(rows) is not list or len(rows) != 7:
        return "MISSING_OR_EXTRA_GRAPH005_EVENTS"
    for row, expected in zip(rows, local):
        if (type(row) is not dict or set(row) != CORE_ROW_KEYS
                or type(row.get("source_event_id")) is not str
                or not EVENT_ID.fullmatch(row["source_event_id"])
                or row["source_event_id"] != expected["source_event_id"]):
            return "FOREIGN_DUPLICATE_OR_REORDERED_GRAPH005_IDS"
        if (row["acme_fixture_full_sha256"] != expected["acme_full_event_sha256"]
                or row["acme_fixture_payload_sha256"] !=
                expected["acme_local_payload_sha256"]):
            return "ACME_FIXTURE_FULL_OR_PAYLOAD_HASH_MISMATCH"
        if (any(type(row[k]) is not str or not HEX64.fullmatch(row[k])
                for k in ("core_pg16_full_event_sha256",
                          "core_pg16_payload_sha256"))
                or row["core_pg16_full_event_sha256"] ==
                row["core_pg16_payload_sha256"]):
            return "INVALID_CORE_FULL_OR_PAYLOAD_HASH_DOMAIN"
    if len({r["source_event_id"] for r in rows}) != 7:
        return "DUPLICATE_GRAPH005_IDS"
    return None


def consume(manifest, *, core_ci_receipt=None, expected_core_head=None,
            expected_receipt_sha256=None):
    """Compare a real disposable Core CI artifact, never grant runtime authority."""
    pinned = bridge.build_receipt(manifest)
    plan = itil.build_receipt(manifest)
    impact = pinned["twin_impact"]
    if (pinned["source_event_count"] != 7 or plan["stage_count"] != 15
            or plan["checkpoint_count"] != 6
            or tuple(impact["path_node_ids"]) != concordance.PATH_NODES
            or tuple(impact["path_edge_ids"]) != concordance.PATH_EDGES
            or impact["source_ci_id"] != "ACME-SAN-FABRIC-A"
            or impact["selected_service_id"] != "ACME-SVC-PAYMENTS"
            or impact["candidate_ci_count"] != 10):
        raise ValueError("unpinned graph-005 Twin or ITIL replay")
    local = pinned["events"]
    result = {
        "schema": SCHEMA, "synthetic": True,
        "provenance": "CORE_DISPOSABLE_CI_ARTIFACT_NOT_RUNTIME_AUTHORITY",
        "seed": pinned["seed"], "graph_version": pinned["graph_version"],
        "source_replay_sha256": pinned["source_replay_sha256"],
        "core_ci_artifact_url": CORE_ARTIFACT_URL,
        "core_ci_source_head": None,
        "core_ci_receipt_sha256": None,
        "core_ci_receipt_status": "UNAVAILABLE",
        "core_ci_receipt_reason": "NO_CORE_CI_RECEIPT_CONSUMED",
        "source_concordance": "UNKNOWN",
        "events": [{
            "sequence": r["sequence"], "source_event_id": r["source_event_id"],
            "ci_id": r["ci_id"],
            "acme_full_event_sha256": r["acme_full_event_sha256"],
            "acme_local_payload_sha256": r["acme_local_payload_sha256"],
            "proposed_core_payload_sha256": r["proposed_core_payload_sha256"],
            "core_pg16_full_event_sha256": None,
            "core_pg16_payload_sha256": None,
            "acme_fixture_hash_comparison": "UNKNOWN",
            "core_vs_acme_full_hash_equivalence": "UNKNOWN",
            "core_vs_acme_payload_hash_equivalence": "UNKNOWN",
        } for r in local],
        "twin_impact": impact,
        "ci_disposable_incident_run": "NOT_ATTESTED",
        "runtime_incident_id": None, "runtime_run_id": None,
        "actor_tenant_acl": "UNKNOWN", "freshness": "UNKNOWN",
        "revocation": "UNKNOWN", "audit_013_014": "UNKNOWN",
        "core_https_runtime_authentication": "NOT_INDEPENDENTLY_ATTESTED",
        "core_pg16_authority": "UNKNOWN",
        "glpi_human_allow": "UNKNOWN", "hitl_approval": "UNKNOWN",
        "observed_payments_impact": "UNKNOWN",
        "itil_stage_count": 15, "verified_stage_count": 0,
        "not_executed_stage_count": 15,
        "stages": [{"stage": r["stage"], "source_event_id": r["source_event_id"],
                    "status": "NOT_EXECUTED", "verification": "UNKNOWN"}
                   for r in plan["stages"]],
        "checkpoint_count": 6, "verified_checkpoint_count": 0,
        "not_executed_checkpoint_count": 6,
        "checkpoints": [{"stage": r["stage"], "status": "NOT_EXECUTED",
                         "verification": "UNKNOWN", "id": None}
                        for r in plan["checkpoints"]],
        "result": "UNKNOWN", "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
        "release_stable": "NO_GO",
    }
    if core_ci_receipt is None:
        return result
    reason = _validate(core_ci_receipt, local, pinned["graph_version"],
                       expected_core_head, expected_receipt_sha256)
    if reason is not None:
        result["core_ci_receipt_status"] = "REJECTED"
        result["core_ci_receipt_reason"] = reason
        return result
    result["core_ci_source_head"] = core_ci_receipt["source_head"]
    result["core_ci_receipt_sha256"] = core_ci_receipt["receipt_sha256"]
    result["core_ci_receipt_status"] = "CI_CONSISTENT_UNTRUSTED"
    result["core_ci_receipt_reason"] = "EXACT_GRAPH005_SEVEN_PG16_CI_ARTIFACT_ONLY"
    result["source_concordance"] = "CONSISTENT_UNTRUSTED"
    result["ci_disposable_incident_run"] = "CI_WRITTEN_REPORTED_ONLY"
    result["audit_013_014"] = "CI_REPORTED_NOT_INDEPENDENTLY_ATTESTED"
    for output, claim in zip(result["events"], core_ci_receipt["events"]):
        output["core_pg16_full_event_sha256"] = claim["core_pg16_full_event_sha256"]
        output["core_pg16_payload_sha256"] = claim["core_pg16_payload_sha256"]
        output["acme_fixture_hash_comparison"] = "MATCH_CI_ONLY"
        output["core_vs_acme_full_hash_equivalence"] = "DISTINCT_DOMAINS_UNKNOWN"
        output["core_vs_acme_payload_hash_equivalence"] = "DISTINCT_SCOPE_UNKNOWN"
    return result


def main():
    parser = argparse.ArgumentParser(description="ACME graph005 Core PG16 CI-only consumer")
    parser.add_argument("--core-ci-receipt", type=Path)
    parser.add_argument("--expected-core-head")
    parser.add_argument("--expected-receipt-sha256")
    parser.add_argument("--expected-file-sha256")
    args = parser.parse_args()
    if args.core_ci_receipt and not all((args.expected_core_head,
                                         args.expected_receipt_sha256,
                                         args.expected_file_sha256)):
        parser.error("Core CI file, head and canonical receipt digests must be pinned")
    core = (_read_untrusted(args.core_ci_receipt,
                            expected_file_sha256=args.expected_file_sha256)
            if args.core_ci_receipt else None)
    output = consume(gen.replay(seed=20261018), core_ci_receipt=core,
                     expected_core_head=args.expected_core_head,
                     expected_receipt_sha256=args.expected_receipt_sha256)
    print(json.dumps(output, sort_keys=True, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
