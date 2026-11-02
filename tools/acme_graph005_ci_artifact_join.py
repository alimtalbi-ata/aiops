"""Read-only, fail-closed cross-artifact graph005/ITIL15 CI receipt.

Core and Worker GitHub CI artifacts can corroborate a pinned synthetic graph,
but they are NOT an independently authenticated same-Incident/Run readback.
No runtime/GLPI/HITL/013/014 authority is conferred by ZIP SHA256, a sidecar,
or a matching source HEAD. No network or service writes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import zipfile
from pathlib import Path

SCHEMA = "aiops.acme.graph005-ci-cross-artifact-itil15.v1"
CORE_FILE = "core-graph005-seven-015.json"
WORKER_FILE = "two-os-negative.json"
GRAPH = "67f0124a2c3b450e5249165e719a5d943fdd7237"
SOURCE_IDS = (
    "SYN-EVT-D339C4CF0B5DD5FBE166", "SYN-EVT-5085CE4F452216CA6368",
    "SYN-EVT-07FBFC9BA5CF807877E9", "SYN-EVT-C09C5E66551CFA5D66E5",
    "SYN-EVT-CA2638D022EF7BBAFFF2", "SYN-EVT-DD341274D02FFBC6763E",
    "SYN-EVT-E3DBA69E2B38BD179315",
)
PHYSICAL = (1, 2, 4, 5, 6, 8, 9)
DOMAINS = {"payload": "aiops.core-source-event-payload.v1",
           "full_event": "aiops.core-full-run-event.v1"}
STAGE_ANCHORS = (
    ("EVENT_ALERT", 1), ("GLPI_TICKET", 1), ("CORE_INCIDENT", 1),
    ("CORE_RUN", 2), ("TWIN_IMPACT_CANDIDATE", 2),
    ("ANALYST", 3), ("CRITIC", 3), ("EVIDENCE", 3),
    ("POLICY_PROPOSAL", 5), ("HITL_APPROVAL", 5), ("SIMULATE", 5),
    ("POST_ACTION_VERIFICATION", 6), ("RESOLUTION", 7),
    ("REOPEN", 7), ("PROBLEM_KNOWLEDGE_CHANGE", 7),
)
CHECKPOINTS = ("GLPI_TICKET", "CORE_INCIDENT", "CORE_RUN", "EVIDENCE",
               "RESOLUTION", "REOPEN")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def read_artifact(path, json_name):
    """Check GitHub ZIP CRC and SHA256 sidecar, not source authenticity."""
    raw = Path(path).read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError("oversized artifact ZIP")
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or z.testzip() is not None:
            raise ValueError("duplicate or corrupt artifact member")
        if any(i.file_size > 1_000_000 or i.is_dir() or
               i.filename.startswith("/") or ".." in Path(i.filename).parts
               for i in infos):
            raise ValueError("unsafe or oversized artifact member")
        sha_name = json_name.removesuffix(".json") + ".sha256"
        if json_name not in names or sha_name not in names:
            raise ValueError("missing artifact JSON or SHA256 sidecar")
        data = z.read(json_name)
        sidecar = z.read(sha_name).decode("ascii").strip().split()
        digest = hashlib.sha256(data).hexdigest()
        if (len(sidecar) != 2 or sidecar[0] != digest or
                Path(sidecar[1]).name != json_name):
            raise ValueError("SHA256 sidecar mismatch")
    return (json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object),
            {"zip_sha256": hashlib.sha256(raw).hexdigest(),
             "json_sha256": digest, "sha256_sidecar_verified": True})


def _inner_receipt_integrity(document, digest_key):
    """Check the producer's unkeyed canonical digest, never its authority."""
    claimed = document.get(digest_key)
    if type(claimed) is not str or not HEX64.fullmatch(claimed):
        return False
    canonical = json.dumps(
        {key: value for key, value in document.items() if key != digest_key},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(canonical).hexdigest() == claimed


def validate(core, worker, expected_head):
    """Return structural reason; never attest actor, tenant or same runtime Run."""
    if type(expected_head) is not str or not HEX40.fullmatch(expected_head):
        return "UNPINNED_EXACT_HEAD"
    if type(core) is not dict or type(worker) is not dict:
        return "MISSING_OR_INVALID_CORE_WORKER_RECEIPT"
    if core.get("source_head") != expected_head or worker.get("source_head") != expected_head:
        return "CROSS_ARTIFACT_EXACT_HEAD_MISMATCH"
    if (core.get("schema") != "aiops.core-graph005-seven-015-source-receipt.v1"
            or worker.get("schema") != "aiops.worker-graph005-two-os-negative.v1"
            or core.get("graph_version") != GRAPH):
        return "FOREIGN_SCHEMA_OR_GRAPH"
    if (core.get("source_fixture_only") is not True or
            core.get("same_run_readback") != "PASS_SYNTHETIC_ONLY" or
            core.get("transport") != "DISPOSABLE_TLS_BASIC_BOUND" or
            core.get("portable_signature") != "NONE" or
            core.get("decision") != "UNKNOWN" or
            core.get("link_status") != "UNKNOWN" or
            core.get("human_glpi_attested") is not False or
            core.get("acme_full_event_equivalence") != "NOT_VERIFIED"):
        return "UNTRUSTED_CORE_AUTHORITY_PROMOTION"
    # Both producer receipts have their own unkeyed canonical digest.
    # A ZIP SHA256 sidecar alone cannot detect rehashed inner JSON mutations.
    # Even valid inner digests are integrity only, not same-Run authentication.
    if (not _inner_receipt_integrity(core, "receipt_sha256") or
            not _inner_receipt_integrity(worker, "payload_sha256")):
        return "CORRUPT_OR_MISSING_INNER_RECEIPT_DIGEST"
    if (core.get("hash_domains") != DOMAINS or
            core.get("source_payload_sequence_domain") != "PINNED_SOURCE_ORDINAL" or
            core.get("source_run_sequence_domain") != "PHYSICAL_RUN_SEQUENCE" or
            core.get("source_payload_ordinals") != list(range(1, 8)) or
            core.get("source_run_sequences") != list(PHYSICAL) or
            type(core.get("same_run_source_count")) is not int or
            core["same_run_source_count"] != 7):
        return "FOREIGN_CORE_HASH_OR_SEQUENCE_DOMAIN"
    rows = core.get("events")
    if type(rows) is not list or len(rows) != 7:
        return "MISSING_OR_EIGHTH_SOURCE"
    full_hashes, payload_hashes = set(), set()
    for i, row in enumerate(rows):
        if type(row) is not dict:
            return "FOREIGN_CORE_SOURCE_ROW"
        full = row.get("core_pg16_full_event_sha256")
        payload = row.get("core_pg16_payload_sha256")
        if (row.get("source_event_id") != SOURCE_IDS[i] or
                type(row.get("pinned_source_ordinal")) is not int or
                row["pinned_source_ordinal"] != i + 1 or
                type(row.get("physical_run_sequence")) is not int or
                row["physical_run_sequence"] != PHYSICAL[i] or
                type(full) is not str or not HEX64.fullmatch(full) or
                type(payload) is not str or not HEX64.fullmatch(payload) or
                full == payload or full in full_hashes or payload in payload_hashes):
            return "FOREIGN_REPLAYED_OR_FORGED_CORE_SOURCE"
        full_hashes.add(full)
        payload_hashes.add(payload)
    if (worker.get("source_ids") != list(SOURCE_IDS) or
            worker.get("source_ordinals") != list(range(1, 8)) or
            worker.get("source_physical_sequences") != list(PHYSICAL)):
        return "WORKER_SOURCE_SET_OR_PHYSICAL_SEQUENCE_MISMATCH"
    if (type(worker.get("worker_os_processes")) is not int or
            worker["worker_os_processes"] != 2 or
            worker.get("distinct_pids") is not True or
            worker.get("pg_major") != 16 or
            worker.get("verification") != "UNVERIFIED" or
            worker.get("human_glpi_attested") is not False or
            worker.get("portable_signature") != "NONE" or
            worker.get("execution_allowed") is not False or
            worker.get("effect_allowed") is not False or
            worker.get("effect_receipts") != 0 or
            worker.get("approve_count") != 0 or
            worker.get("temporal_signal_count") != 0 or
            worker.get("core_terminal_014_exercised") is not False or
            worker.get("core_outbox_replay_exercised") is not False or
            worker.get("source_after_revocation") != "UNKNOWN" or
            worker.get("reopen") != "RECOMMENDED_NOT_EXECUTED"):
        return "UNTRUSTED_WORKER_OR_HUMAN_AUTHORITY_PROMOTION"
    return None


def build_receipt(core, worker, expected_head, *, core_artifact=None,
                  worker_artifact=None, host_sidecar=None):
    reason = validate(core, worker, expected_head)
    matched = reason is None
    # A source HEAD and synthetic IDs overlap, but the Worker artifact does NOT
    # expose independently authenticated Incident/Run/actor/tenant.
    stages = [{"stage": name, "source_ordinal": ordinal,
               "source_event_id": SOURCE_IDS[ordinal - 1],
               "physical_run_sequence": PHYSICAL[ordinal - 1],
               "status": "NOT_EXECUTED", "verification": "UNKNOWN",
               "runtime_id": None, "runtime_evidence_ids": []}
              for name, ordinal in STAGE_ANCHORS]
    return {
        "schema": SCHEMA, "source_head": expected_head,
        "core_artifact": core_artifact, "worker_artifact": worker_artifact,
        "cross_artifact_concordance": "CONSISTENT_UNTRUSTED" if matched else "UNKNOWN",
        "cross_artifact_reason": "MATCHING_SYNTHETIC_SHAPE_NOT_SAME_RUN_PROOF"
        if matched else reason,
        "independent_core_worker_same_run": "NOT_ATTESTED",
        "independent_actor_tenant_incident_run": "NOT_ATTESTED",
        "core_https_runtime_authentication": "NOT_ATTESTED",
        "core_014_terminal_worker_join": "NOT_ATTESTED",
        "core_015_source_immutable_provenance": "CI_DISPOSABLE_ONLY",
        "worker_two_os_processes": "CI_DISPOSABLE_ONLY" if matched else "UNKNOWN",
        "durable_replay_fence": "NOT_ATTESTED",
        "portable_signature": "NONE", "glpi_human_allow": "NOT_ATTESTED",
        "hitl_approval": "NOT_ATTESTED", "observed_payments_outage": "UNKNOWN",
        "source_event_ids": list(SOURCE_IDS),
        "source_ordinals": list(range(1, 8)),
        "physical_run_sequences": list(PHYSICAL),
        "twin_impact": {"source_ci": "ACME-SAN-FABRIC-A",
                        "service": "ACME-SVC-PAYMENTS",
                        "candidate_impacted_ci_count": 10,
                        "observed_impact": "UNKNOWN"},
        "stage_count": 15, "verified_stage_count": 0,
        "not_executed_stage_count": 15, "stages": stages,
        "checkpoint_count": 6, "verified_checkpoint_count": 0,
        "not_executed_checkpoint_count": 6,
        "checkpoints": [{"stage": s, "status": "NOT_EXECUTED", "id": None}
                        for s in CHECKPOINTS],
        "runtime_incident_id": None, "runtime_run_id": None,
        "runtime_ticket_id": None, "runtime_evidence_ids": [],
        "runtime_e2e": "NOT_EXECUTED", "simulation_executed": False,
        "resolution_verified": False, "reopen_verified": False,
        "publishable_to_core_or_glpi": False, "live_effects_authorized": False,
        "release_stable": "NO_GO",
        "portal_host_readonly": (assess_host_readonly(host_sidecar)
                                 if host_sidecar is not None else None),
    }


def negative_controls(core, worker, expected_head):
    """Executable mutation tests: every forged/foreign receipt must fail closed."""
    cases = (
        ("core_nonanchor_source_substitution", "core", lambda x: x["events"][2].update(source_event_id="SYN-EVT-" + "F" * 20)),
        ("core_physical_as_ordinal", "core", lambda x: x["events"][2].update(physical_run_sequence=3)),
        ("core_hash_domain_swap", "core", lambda x: x["hash_domains"].update(payload=DOMAINS["full_event"], full_event=DOMAINS["payload"])),
        ("core_hash_domain_collapse", "core", lambda x: x["events"][4].update(core_pg16_full_event_sha256=x["events"][4]["core_pg16_payload_sha256"])),
        ("worker_foreign_source", "worker", lambda x: x["source_ids"].__setitem__(6, "SYN-EVT-" + "F" * 20)),
        ("worker_wrong_physical", "worker", lambda x: x["source_physical_sequences"].__setitem__(5, 6)),
        ("worker_forged_human_allow", "worker", lambda x: x.update(human_glpi_attested=True, approve_count=1)),
        ("core_fake_signed_provenance", "core", lambda x: x.update(portable_signature="SIGNED")),
        ("worker_fake_terminal_outbox", "worker", lambda x: x.update(core_terminal_014_exercised=True, core_outbox_replay_exercised=True)),
    )
    out = []
    for name, owner, mutate in cases:
        c, w = copy.deepcopy(core), copy.deepcopy(worker)
        mutate(c if owner == "core" else w)
        reason = validate(c, w, expected_head)
        if reason is None:
            raise AssertionError("negative mutation accepted: " + name)
        out.append({"case": name, "verdict": "REJECTED", "reason": reason})
    return out



HOST_ANONYMOUS_CONTRACTS = (
    ("health", "/health", 200),
    ("shell", "/", 200),
    ("itsm_shell", "/itsm", 200),
    ("oidc_session", "/api/portal/session", 401),
    ("bootstrap", "/api/portal/bootstrap", 401),
    ("components", "/api/portal/components", 401),
    ("glpi_authority", "/api/portal/itsm", 401),
    ("noc_runtime", "/api/noc/runtime-state", 401),
    ("noc_correlation", "/api/noc/correlation", 401),
)


def assess_host_readonly(sidecar):
    """Classify a redacted Debian sidecar as shape only, never human authority.

    Even a valid 9/9 report is self-described host telemetry, not authenticated
    Core 015/014, IdP READMY, GLPI ALLOW, or an executed ITIL stage.
    """
    reason = None
    if type(sidecar) is not dict or sidecar.get("schema") != "aiops.debian-poller-qualification.v1":
        reason = "FOREIGN_OR_MISSING_HOST_SCHEMA"
    else:
        portal = sidecar.get("portal")
        preflight = sidecar.get("deployment_preflight")
        contracts = sidecar.get("portal_nine_readonly_contracts")
        if any(type(x) is not dict for x in (portal, preflight, contracts)):
            reason = "MISSING_HOST_CONTRACTS"
        else:
            image = portal.get("image_id")
            bindings = portal.get("bindings")
            if (type(image) is not str or not image.startswith("sha256:") or
                    not HEX64.fullmatch(image.removeprefix("sha256:")) or
                    preflight.get("deployed_image_id") != image or
                    contracts.get("image_id") != image or
                    portal.get("state") != "running" or
                    portal.get("health") != "healthy" or
                    type(bindings) is not list or
                    not any(type(b) is dict and b.get("host_port") == 7777 and
                            b.get("host_ip") == "0.0.0.0" for b in bindings) or
                    preflight.get("portal_env_port_7777") is not True or
                    preflight.get("portal_host_port_7777") is not True or
                    preflight.get("verdict") != "DEPLOYED_HEALTH_PASS_E2E_PENDING" or
                    sidecar.get("http_7777") != {"status": 200, "qualified": True}):
                reason = "PORTAL_IMAGE_OR_STRICT_HEALTH_MISMATCH"
            elif (contracts.get("status") != "PASS_READONLY_ONLY" or
                  type(contracts.get("total")) is not int or contracts["total"] != 9 or
                  type(contracts.get("passed")) is not int or contracts["passed"] != 9 or
                  contracts.get("acme_e2e") !=
                  "BLOCKED_NO_INDEPENDENT_HUMAN_GLPI_IDP_AUTHORITY" or
                  any(contracts.get(k) is not None for k in
                      ("incident_id", "run_id", "glpi_ticket_id")) or
                  sidecar.get("external_tls_sso_glpi_e2e") != "NOT_VERIFIED" or
                  sidecar.get("release_stable") != "NO_GO"):
                reason = "HOST_RUNTIME_OR_HUMAN_AUTHORITY_PROMOTION"
            else:
                checks = contracts.get("checks")
                if (type(checks) is not list or len(checks) != 9 or
                        any(type(c) is not dict or c.get("status") != "PASS"
                            for c in checks) or
                        [(c.get("name"), c.get("path"), c.get("http_status"))
                         for c in checks] != list(HOST_ANONYMOUS_CONTRACTS)):
                    reason = "FOREIGN_OR_PROMOTED_ANONYMOUS_HTTP_CONTRACT"
    return {
        "classification": "CONSISTENT_UNTRUSTED" if reason is None else "UNKNOWN",
        "reason": "NINE_ANONYMOUS_GETS_NOT_HUMAN_GLPI_E2E" if reason is None else reason,
        "anonymous_gets_shape_matched": 9 if reason is None else 0,
        "independently_authenticated_host_receipt": "NOT_ATTESTED",
        "independent_core_worker_same_run": "NOT_ATTESTED",
        "human_idp_glpi_authority": "NOT_ATTESTED",
        "itil_stage_execution": "NOT_EXECUTED",
        "release_stable": "NO_GO",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-zip", type=Path, required=True)
    parser.add_argument("--worker-zip", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--host-sidecar", type=Path, help="Redacted read-only Debian sidecar; never human authority")
    args = parser.parse_args()
    core, core_meta = read_artifact(args.core_zip, CORE_FILE)
    worker, worker_meta = read_artifact(args.worker_zip, WORKER_FILE)
    host_sidecar = None
    if args.host_sidecar is not None:
        if args.host_sidecar.stat().st_size > 250_000:
            raise ValueError("oversized host sidecar")
        host_sidecar = json.loads(args.host_sidecar.read_text(encoding="utf-8"),
                                  object_pairs_hook=_unique_object)
    receipt = build_receipt(core, worker, args.expected_head,
                            core_artifact=core_meta, worker_artifact=worker_meta,
                            host_sidecar=host_sidecar)
    if receipt["cross_artifact_concordance"] != "CONSISTENT_UNTRUSTED":
        receipt["negative_controls"] = []
    else:
        receipt["negative_controls"] = negative_controls(core, worker, args.expected_head)
    data = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
