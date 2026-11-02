"""ACME-only disposable 15-stage SAN->Payments projection over Core graph005.

This is an executable structural contract, not an E2E execution. Core receipt
checksums, caller-provided Worker rows, synthetic Twin edges, and even
GLPI/Evidence-shaped ALLOW objects have no portable human or runtime authority.
No network, host, GLPI, Core, Temporal or LIVE write occurs here.
"""
from __future__ import annotations

from tools import acme_graph005_same_run_consumer as same_run
from tools import acme_synthetic_itil_stage_authority_consumer as itil

SCHEMA = "aiops.acme.graph005-itil-15-stage-disposable.v1"


def consume(manifest, *, receipt=None, run_events=None, claims=None,
            expected=None, record=None, source_issuer=None, now=None,
            seen_receipt_hashes=None, glpi_receipt=None,
            evidence_receipt=None, stage_candidate=None):
    """Project pinned stage anchors only after strict same-Run shape checking.

    A structurally matching readback is CONSISTENT_UNTRUSTED, not signed.
    In particular this method cannot independently authenticate the Core TLS
    peer, IdP subject, GLPI User/Profile/Entity/Ticket, 013/014 audit, or a
    durable replay fence. It never promotes a stage to executed or verified.
    """
    plan = itil.consume(
        manifest, candidate=stage_candidate,
        glpi_receipt=glpi_receipt, evidence_receipt=evidence_receipt)
    joined = same_run.consume_joined_worker_projection(
        manifest, run_events=run_events, receipt=receipt,
        claims=claims, expected=expected, record=record,
        source_issuer=source_issuer, now=now,
        seen_receipt_hashes=seen_receipt_hashes)

    events = joined["events"]
    if (len(events) != 7 or plan["source_event_count"] != 7
            or plan["graph_version"] != joined["graph_version"]
            or plan["source_replay_sha256"] != joined["source_replay_sha256"]
            or len(plan["stages"]) != 15 or len(plan["checkpoints"]) != 6):
        raise ValueError("unmatched pinned graph005/ITIL fixture")

    # The 15 stage anchors are synthetic source ordinals, not physical Run
    # sequence numbers. The Worker harness interleaves 3/7 and appends 10.
    stages = []
    for anchor in plan["stages"]:
        ordinal = anchor["source_step"]
        if type(ordinal) is not int or not 1 <= ordinal <= 7:
            raise ValueError("untrusted stage source ordinal")
        row = events[ordinal - 1]
        if (anchor["source_event_id"] != row["source_event_id"]
                or anchor["acme_full_event_sha256"] !=
                row["acme_fixture_full_sha256"]
                or anchor["status"] != "NOT_EXECUTED"
                or anchor["verification"] != "UNKNOWN"
                or anchor["runtime_id"] is not None
                or anchor["runtime_evidence_ids"] != []):
            raise ValueError("untrusted stage source or runtime promotion")
        stages.append({
            "stage": anchor["stage"],
            "source_ordinal": ordinal,
            "physical_run_sequence": same_run.PHYSICAL_SEQUENCES[ordinal - 1],
            "source_event_id": row["source_event_id"],
            "fixture_full_sha256": row["acme_fixture_full_sha256"],
            "fixture_payload_sha256": row["acme_fixture_payload_sha256"],
            "core_full_sha256_untrusted": None,
            "core_payload_sha256_untrusted": None,
            "runtime_checkpoint": anchor["runtime_checkpoint"],
            "status": "NOT_EXECUTED",
            "verification": "UNKNOWN",
            "runtime_id": None,
            "runtime_evidence_ids": [],
        })

    shape_match = (joined["source_concordance"] == "CONSISTENT_UNTRUSTED"
                   and joined["worker_projection_concordance"] ==
                   "CONSISTENT_UNTRUSTED")
    if shape_match:
        for anchor in stages:
            core = events[anchor["source_ordinal"] - 1]
            if (core["domain_equivalence"] !=
                    "DISTINCT_DOMAINS_NOT_EQUIVALENT"):
                raise ValueError("untrusted hash-domain equivalence")
            anchor["core_full_sha256_untrusted"] = core["core_full_event_sha256"]
            anchor["core_payload_sha256_untrusted"] = core["core_payload_sha256"]

    checkpoints = [{
        "stage": c["stage"], "status": "NOT_EXECUTED",
        "id": None, "verification": "UNKNOWN",
    } for c in plan["checkpoints"]]
    if any(c["status"] != "NOT_EXECUTED" or c["id"] is not None
           for c in plan["checkpoints"]):
        raise ValueError("untrusted human/runtime checkpoint")

    impact = joined["twin_impact"]
    if (impact["candidate_ci_count"] != 10
            or impact["source_ci_id"] != "ACME-SAN-FABRIC-A"
            or impact["selected_service_id"] != "ACME-SVC-PAYMENTS"
            or impact["observed_service_impact"] != "UNKNOWN"):
        raise ValueError("untrusted Twin impact authority")

    return {
        "schema": SCHEMA,
        "synthetic": True,
        "graph_version": joined["graph_version"],
        "source_replay_sha256": joined["source_replay_sha256"],
        "source_ordinals": list(range(1, 8)),
        "physical_run_sequences": list(same_run.PHYSICAL_SEQUENCES),
        "source_concordance": joined["source_concordance"],
        "source_reason": joined["source_reason"],
        "worker_projection_concordance": joined["worker_projection_concordance"],
        "worker_projection_reason": joined["worker_projection_reason"],
        "contract_status": "CONSISTENT_UNTRUSTED" if shape_match else "UNKNOWN",
        "source_provenance": "NONPORTABLE_SHAPE_ONLY" if shape_match else "UNKNOWN",
        "core_https_runtime_authentication": joined["core_https_runtime_authentication"],
        "core_pg16_authority": "UNKNOWN",
        "actor_idp_authority": "UNKNOWN",
        "tenant_actor_scope": joined["tenant_actor_scope"],
        "freshness": joined["freshness"],
        "revocation": joined["revocation"],
        "durable_replay_fence": "NOT_ATTESTED",
        "core_terminal_014_joined": "NOT_ATTESTED",
        "core_outbox_replay_joined": "NOT_ATTESTED",
        "worker_production_authority": "UNKNOWN",
        "glpi_receipt_shape": plan["authority"]["glpi_readback"],
        "evidence_receipt_shape": plan["authority"]["evidence_readback"],
        "glpi_human_allow": "NOT_ATTESTED",
        "hitl_approval": "NOT_ATTESTED",
        "runtime_incident_id": None,
        "runtime_run_id": None,
        "runtime_ticket_id": None,
        "runtime_evidence_ids": [],
        "stage_count": 15, "verified_stage_count": 0,
        "not_executed_stage_count": 15, "stages": stages,
        "checkpoint_count": 6, "verified_checkpoint_count": 0,
        "not_executed_checkpoint_count": 6, "checkpoints": checkpoints,
        "twin_impact": {
            "source_ci_id": impact["source_ci_id"],
            "selected_service_id": impact["selected_service_id"],
            "candidate_ci_count": 10,
            "candidate_service_ids": impact["candidate_service_ids"],
            "path_node_ids": impact["path_node_ids"],
            "path_edge_ids": impact["path_edge_ids"],
            "observed_service_impact": "UNKNOWN",
            "causality_verified": False,
        },
        "simulation_executed": False,
        "post_action_verified": False,
        "resolution_verified": False,
        "reopen_verified": False,
        "runtime_e2e": "NOT_EXECUTED",
        "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False,
        "release_stable": "NO_GO",
    }
