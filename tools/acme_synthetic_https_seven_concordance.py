"""ACME-only offline consumer of the Core HTTPS seven-source adapter response.

No HTTP request, database write, TLS assertion, GLPI approval, or runtime ID is
created here. A test-controlled 200 response is only CONSISTENT_UNTRUSTED:
source service issuer and actor IdP issuer are separate trust domains.
"""
import argparse
import json
from pathlib import Path

from tools import acme_synthetic_pg16_seven_bridge as bridge
from tools import generate_acme_incidents as gen

SCHEMA = "aiops.acme.https-seven-twin-concordance.v1"
FIXTURE = (gen.ROOT / "docs/customer-story" /
           "ACME-HTTPS-SEVEN-TWIN-CONCORDANCE-UNKNOWN-2026-11-01.json")
PATH_NODES = ("ACME-SAN-FABRIC-A", "ACME-STO-PURE01",
              "ACME-VM-PAY01", "ACME-APP-ORACLEPAY", "ACME-SVC-PAYMENTS")
PATH_EDGES = ("ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02")


def build_receipt(manifest):
    """Redacted canonical seven-event/graph matrix; no positive Core authority."""
    local = bridge.build_receipt(manifest)
    impact = local["twin_impact"]
    if (local["seed"] != 20261018
            or local["graph_version"] != gen.SEED_GIT_BLOB
            or tuple(impact["path_node_ids"]) != PATH_NODES
            or tuple(impact["path_edge_ids"]) != PATH_EDGES
            or impact["selected_service_id"] != "ACME-SVC-PAYMENTS"
            or impact["source_ci_id"] != "ACME-SAN-FABRIC-A"
            or local["source_event_count"] != 7
            or any(not e["source_event_id"].startswith("SYN-EVT-")
                   for e in local["events"])):
        raise ValueError("noncanonical ACME graph 005 or source events")
    return {
        "schema": SCHEMA, "synthetic": True,
        "provenance": "SYNTHETIC_FIXTURE_ONLY",
        "seed": local["seed"], "graph_version": local["graph_version"],
        "source_replay_sha256": local["source_replay_sha256"],
        "core_https_adapter_path": "/v2/canonical-seven-readback",
        "core_producer_schema": bridge.CORE_SCHEMA,
        "source_issuer_domain": "CORE_SOURCE_ISSUER_SEPARATE_FROM_ACTOR_IDP",
        "actor_issuer_domain": "ACTOR_IDP_ISSUER_SEPARATE_FROM_CORE_SOURCE",
        "source_event_count": 7,
        "events": [{
            "sequence": e["sequence"], "source_event_id": e["source_event_id"],
            "ci_id": e["ci_id"],
            "acme_full_event_sha256": e["acme_full_event_sha256"],
            "acme_local_payload_sha256": e["acme_local_payload_sha256"],
            "proposed_core_payload_sha256": e["proposed_core_payload_sha256"],
            "core_pg16_full_event_sha256": None,
            "core_pg16_payload_sha256": None,
            "comparison": "UNKNOWN",
        } for e in local["events"]],
        "twin_impact": impact,
        "core_https_response": "UNAVAILABLE",
        "core_source_shape": "UNAVAILABLE",
        "core_source_reason": "NO_AUTHENTICATED_CORE_PG16_READBACK",
        "compared_event_count": 0,
        "candidate_incident": {"count": 1, "id": None, "status": "NOT_CREATED"},
        "runtime": {
            "tenant_id": None, "actor_subject": None, "incident_id": None,
            "run_id": None, "glpi_ticket_id": None, "evidence_ids": [],
        },
        "core_pg16_authority": "UNKNOWN",
        "actor_tenant_acl": "UNKNOWN", "immutable_audit_013_014": "UNKNOWN",
        "freshness": "UNKNOWN", "revocation": "UNKNOWN",
        "glpi_human_allow": False, "hitl_approval": None,
        "itil_stages": {"count": 15, "verified": 0, "not_executed": 15,
                        "status": "NOT_EXECUTED"},
        "checkpoints": {"count": 6, "verified": 0, "not_executed": 6,
                        "status": "NOT_EXECUTED"},
        "result": "UNKNOWN", "live_effects_authorized": False,
    }


def consume_adapter_response(manifest, *, http_status, response,
                             source_issuer, actor_issuer,
                             expected_source_issuer, expected_actor_issuer,
                             now):
    """Consume a *separately supplied* Core adapter response, fail-closed.

    An HTTP 200 from a mocked/disposable adapter is not proof of TLS peer,
    actor IdP verification, PG16 transaction, immutable 013/014 or GLPI rights.
    The caller must not turn this informational matrix into an ALLOW decision.
    """
    result = build_receipt(manifest)
    if (any(type(x) is not str or not x for x in
            (source_issuer, actor_issuer,
             expected_source_issuer, expected_actor_issuer))
            or expected_source_issuer == expected_actor_issuer
            or source_issuer == actor_issuer):
        result["core_source_reason"] = "UNPINNED_OR_CONFLATED_ISSUER_DOMAINS"
        result["core_https_response"] = "REJECTED"
        return result
    if http_status != 200:
        result["core_https_response"] = "UNAVAILABLE" if http_status == 503 else "REJECTED"
        result["core_source_reason"] = "CORE_HTTPS_NEGATIVE_OR_UNAVAILABLE"
        return result
    if (type(response) is not dict
            or source_issuer != expected_source_issuer
            or actor_issuer != expected_actor_issuer
            or response.get("issuer") != expected_source_issuer
            or response.get("actor_issuer") != expected_actor_issuer):
        result["core_https_response"] = "REJECTED"
        result["core_source_reason"] = "FOREIGN_SOURCE_OR_ACTOR_ISSUER"
        return result
    compared = bridge.consume(manifest, core_proof=response, now=now)
    result["core_https_response"] = "TEST_CONTROLLED_200_NOT_AUTHORITY"
    result["core_source_shape"] = compared["core_proof_shape"]
    result["core_source_reason"] = compared["core_proof_reason"]
    result["compared_event_count"] = compared["compared_event_count"]
    if compared["core_proof_shape"] == "CONSISTENT_UNTRUSTED":
        for local, row in zip(result["events"], compared["events"]):
            if local["source_event_id"] != row["source_event_id"]:
                raise ValueError("unexpected ACME/Core row order")
            local["comparison"] = (
                row["core_full_vs_acme_full"] + " / " +
                row["core_payload_vs_local_proposal"])
    # Never copy raw actor, tenant, Incident, Run, Evidence or GLPI IDs.
    return result


def main():
    parser = argparse.ArgumentParser(description="ACME Core HTTPS source concordance")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = gen.replay(seed=20261018)
    result = build_receipt(manifest)
    if args.check:
        stored = bridge._read_untrusted(FIXTURE)
        if gen._canonical(stored) != gen._canonical(result):
            raise ValueError("ACME HTTPS source concordance receipt changed")
        print(json.dumps({"check": "PASS_SYNTHETIC_ONLY", "events": 7,
                          "core_pg16_authority": "UNKNOWN",
                          "itil_not_executed": 15,
                          "checkpoints_not_executed": 6}, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
