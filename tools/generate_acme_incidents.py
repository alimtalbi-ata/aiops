#!/usr/bin/env python3
"""Offline ACME graph-bound SYNTHETIC event replay. No API, DB or GLPI writes.

Reuses main's 005_seed_acme.sql graph/scenario steps and the seeded-random
pattern from historical #185 generate_acme_telemetry_v291.py; deliberately
never imports or launches the simulator's effectful /api/launch route.
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
SEED_FILE = ROOT / "db/migrations/005_seed_acme.sql"
CATALOG_FILE = ROOT / "tests/fixtures/acme_enterprise_incident_catalog_v1.json"
SEED_GIT_BLOB = "67f0124a2c3b450e5249165e719a5d943fdd7237"
CATALOG_GIT_BLOB = "78e749c623d7ee7ea1d33a74577b4f7b696f3207"
GOVERNANCE_SOURCE_FILE = ROOT / "tests/fixtures/acme_twin_governance_source_index_v1.json"
GOVERNANCE_SOURCE_GIT_BLOB = "e77a0abbb53176488ec49d7c0c9f8581d4620b3f"
VERTICAL_CONTRACT_FILE = ROOT / "tests/fixtures/acme_synthetic_vertical_contract_v1.json"
VERTICAL_CONTRACT_GIT_BLOB = "e74e7b67d0d58e8eb1c2e4b54b1b0bf688694d13"
EVENT_IMPACT_CONTRACT_FILE = ROOT / "tests/fixtures/acme_synthetic_event_impact_contract_v1.json"
EVENT_IMPACT_CONTRACT_GIT_BLOB = "10a0dac5d41d39ce115e29d6363c458148361496"
SOURCE = "ACME_OFFLINE_SYNTHETIC_REPLAY_V1"
ANCHOR = datetime(2026, 10, 31, 9, 42, tzinfo=timezone.utc)  # fixture clock, NOT wall clock
NODE_RE = re.compile(r"^\('(ACME-[^']+)','(BUSINESS|SERVICE|APPLICATION|VM|SERVER|STORAGE|SAN|NETWORK|NAS)','[^']+','[^']+','[^']+',([1-5]),", re.M)
EDGE_RE = re.compile(r"\('(ACME-E\d{2})','([^']+)','([^']+)','([^']+)',(\d+),([.\d]+)\)")
SCENARIO_RE = re.compile(r"\('(SCN-[^']+)','[^']+',(\d+),true,'[^']+'\)")
STEP_RE = re.compile(r"\('SCN-GOLDEN-PAYMENT-P1',(\d+),(\d+),'([^']+)','([^']+)','([^']+)'\)")
PRIORITY = {
    "HIGH": {"CRITICAL": "P1", "HIGH": "P2", "MEDIUM": "P3", "LOW": "P3"},
    "MEDIUM": {"CRITICAL": "P2", "HIGH": "P3", "MEDIUM": "P3", "LOW": "P4"},
    "LOW": {"CRITICAL": "P3", "HIGH": "P3", "MEDIUM": "P4", "LOW": "P4"},
}
CHECKPOINTS = ("GLPI_TICKET", "CORE_INCIDENT", "CORE_RUN", "EVIDENCE", "RESOLUTION", "REOPEN")


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _strict_fixture_equal(actual, pinned):
    """Compare injected fixture structures without Python bool/int/float aliases.

    The graph contains sets and tuples, so canonical JSON alone cannot be
    used here. This check does not grant runtime or tenant authority.
    """
    if type(actual) is not type(pinned):
        return False
    if isinstance(pinned, dict):
        return (actual.keys() == pinned.keys() and
                all(_strict_fixture_equal(actual[key], value)
                    for key, value in pinned.items()))
    if isinstance(pinned, (list, tuple)):
        return (len(actual) == len(pinned) and
                all(_strict_fixture_equal(a, b) for a, b in zip(actual, pinned)))
    if isinstance(pinned, (set, frozenset)):
        return (len(actual) == len(pinned) and
                all(any(_strict_fixture_equal(a, b) for a in actual) for b in pinned))
    return type(actual) is type(pinned) and actual == pinned


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key: " + key)
        out[key] = value
    return out


def _git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _stamp(seconds):
    return (ANCHOR + timedelta(seconds=seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_graph(path=SEED_FILE):
    raw = Path(path).read_bytes()
    if _git_blob(raw) != SEED_GIT_BLOB:
        raise ValueError("seed graph Git blob mismatch; no unreviewed topology")
    sql = raw.decode("utf-8")
    node_rows = NODE_RE.findall(sql)
    edge_rows = EDGE_RE.findall(sql)
    step_rows = STEP_RE.findall(sql)
    scenario_rows = SCENARIO_RE.findall(sql)
    nodes = {node: {"type": kind, "criticality": int(criticality)}
             for node, kind, criticality in node_rows}
    edges = {eid: {"source_id": src, "target_id": dst,
                   "relation_type": relation, "redundancy": int(redundancy)}
             for eid, src, dst, relation, redundancy, _ in edge_rows}
    if (len(nodes) != 18 or len(node_rows) != 18 or len(edges) != 17 or
            len(edge_rows) != 17 or len(step_rows) != 7 or len(scenario_rows) != 4):
        raise ValueError("ambiguous graph or golden scenario steps")
    if any(e["source_id"] not in nodes or e["target_id"] not in nodes
           for e in edges.values()):
        raise ValueError("dangling graph edge")
    steps = [(int(n), int(t), action, ci, json.loads(payload, object_pairs_hook=_unique_object))
             for n, t, action, ci, payload in step_rows]
    if [n for n, *_ in steps] != list(range(1, 8)) or any(ci not in nodes for _, _, _, ci, _ in steps):
        raise ValueError("invalid golden scenario step references")
    # Consumer -> dependency is the stored direction. Impact *candidates* traverse reverse.
    consumers = {node: [] for node in nodes}
    for eid, edge in edges.items():
        consumers[edge["target_id"]].append((eid, edge["source_id"]))
    for items in consumers.values():
        items.sort()
    return {"nodes": nodes, "edges": edges, "consumers": consumers, "steps": steps,
            "graph_version": SEED_GIT_BLOB, "scenario_ids": {sid for sid, _ in scenario_rows}}


def load_catalog(path=CATALOG_FILE):
    raw = Path(path).read_bytes()
    if _git_blob(raw) != CATALOG_GIT_BLOB:
        raise ValueError("catalog Git blob mismatch; no unreviewed scenario parameters")
    data = json.loads(raw, object_pairs_hook=_unique_object)
    if (data.get("schema") != "aiops.acme.synthetic-incident-catalog.v1" or
            data.get("graph_git_blob") != SEED_GIT_BLOB or
            data.get("source") != "db/migrations/005_seed_acme.sql" or
            data.get("provenance") != "SYNTHETIC_FIXTURE" or
            data.get("tenant_scope") != "UNKNOWN" or
            data.get("observed_at") is not None or data.get("known_at") is not None or
            data.get("freshness") != "UNKNOWN" or
            data.get("live_effects_authorized") is not False):
        raise ValueError("catalog provenance or source mismatch")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 10:
        raise ValueError("expected exactly ten catalog categories")
    keys = [s.get("key") for s in scenarios]
    if any(not isinstance(k, str) for k in keys) or len(set(keys)) != 10:
        raise ValueError("duplicate or invalid scenario category")
    for s in scenarios:
        if (s.get("severity_synthetic") not in ("P1", "P2", "P3", "P4") or
                s.get("urgency_synthetic") not in ("CRITICAL", "HIGH", "MEDIUM", "LOW") or
                type(s.get("frequency_seconds")) is not int or
                type(s.get("duration_seconds")) is not int or
                not 0 < s["frequency_seconds"] <= s["duration_seconds"] <= 86400 or
                s.get("blast_radius") != "REVERSE_DEPENDENCY_CANDIDATES_ONLY" or
                s.get("recovery") != "CHECKPOINT_ONLY_NOT_VERIFIED"):
            raise ValueError("invalid scenario parameters")
        supported = s.get("status") == "SUPPORTED_BY_SEED"
        if supported != (s.get("source_ci_id") is not None and s.get("service_id") is not None):
            raise ValueError("unsupported category must not invent CI/service IDs")
        if not supported and (s.get("status") != "BLOCKED_MISSING_CMDB_CI" or
                              not s.get("blocker")):
            raise ValueError("unsupported category missing actionable blocker")
        allowed_ids = {"REDUNDANT_SAN_PATH_LOSS": "SCN-GOLDEN-PAYMENT-P1",
                       "CAPACITY_PRESSURE": "SCN-STORAGE-CAPACITY-P2"}
        if s.get("scenario_id") != allowed_ids.get(s["key"]):
            raise ValueError("scenario_id not registered for this catalog category")
        if s.get("maintenance_window") is not None:
            w = s["maintenance_window"]
            if (not isinstance(w, dict) or
                    type(w.get("start_offset_seconds")) is not int or
                    type(w.get("end_offset_seconds")) is not int or
                    not 0 <= w["start_offset_seconds"] < w["end_offset_seconds"] <= s["duration_seconds"]):
                raise ValueError("invalid synthetic maintenance window")
    return data, hashlib.sha256(raw).hexdigest()


def load_governance_source_index(path=None):
    """Read only pinned source *pointers*, never invented governance records.

    A source pointer is not a real DC/owner/SLA/OLA/Change authority.
    Changes require review of this exact Git blob and the underlying source.
    """
    path = GOVERNANCE_SOURCE_FILE if path is None else path
    raw = Path(path).read_bytes()
    if _git_blob(raw) != GOVERNANCE_SOURCE_GIT_BLOB:
        raise ValueError("governance source index Git blob mismatch")
    data = json.loads(raw, object_pairs_hook=_unique_object)
    if (data.get("schema") != "aiops.acme.synthetic-governance-source-index.v1" or
            data.get("provenance") != "SYNTHETIC_FIXTURE" or
            data.get("tenant_scope") != "UNKNOWN" or
            data.get("graph_git_blob") != SEED_GIT_BLOB or
            data.get("catalog_git_blob") != CATALOG_GIT_BLOB):
        raise ValueError("governance source index provenance mismatch")
    supported = {
        "site": ("SYNTHETIC_NODE_ONLY", "db/migrations/005_seed_acme.sql", "twin_nodes.site"),
        "service_criticality_synthetic_1_to_5": (
            "SYNTHETIC_NODE_ONLY", "db/migrations/005_seed_acme.sql", "twin_nodes.criticality"),
        "blast_radius_candidate_service_ids": (
            "SYNTHETIC_CANDIDATE_ONLY", "db/migrations/005_seed_acme.sql",
            "twin_edges.consumer_to_dependency_reverse_reachability"),
        "maintenance_window_synthetic": (
            "SYNTHETIC_SCENARIO_ONLY",
            "tests/fixtures/acme_enterprise_incident_catalog_v1.json",
            "scenarios[].maintenance_window"),
        "change_lookup": (
            "PLANNED_STEP_ONLY", "db/migrations/005_seed_acme.sql",
            "scenario_steps.CHANGE_LOOKUP"),
    }
    absent = {"datacenter_id", "datacenter_relation", "service_owner_id",
              "service_team_id", "sla_id", "ola_id", "change_id",
              "maintenance_actual"}
    expected = {field: {"authority": status, "source": source, "selector": selector}
                for field, (status, source, selector) in supported.items()}
    expected.update({field: {"authority": "UNKNOWN", "source": None, "selector": None}
                     for field in absent})
    if _canonical(data.get("fields")) != _canonical(expected):
        raise ValueError("governance source index unsupported authority")
    return data


def dependency_candidates(graph, source_ci, service_id):
    if source_ci not in graph["nodes"] or service_id not in graph["nodes"]:
        raise ValueError("unknown source or service CI")
    queue = deque([source_ci])
    paths = {source_ci: ([], [source_ci])}
    while queue:
        node = queue.popleft()
        for eid, consumer in graph["consumers"][node]:
            if consumer not in paths:
                edge_ids, node_ids = paths[node]
                paths[consumer] = (edge_ids + [eid], node_ids + [consumer])
                queue.append(consumer)
    if service_id not in paths or graph["nodes"][service_id]["type"] != "SERVICE":
        raise ValueError("catalog target is not a graph-dependent service")
    services = sorted(ci for ci in paths if graph["nodes"][ci]["type"] == "SERVICE")
    max_criticality = max(graph["nodes"][ci]["criticality"] for ci in services)
    impact = "HIGH" if max_criticality >= 5 else "MEDIUM" if max_criticality >= 3 else "LOW"
    edges, nodes = paths[service_id]
    return {"source_ci_id": source_ci, "selected_service_id": service_id,
            "candidate_service_ids": services, "candidate_ci_count": len(paths),
            "path_edge_ids": edges, "path_node_ids": nodes,
            "estimated_impact_level": impact, "observed_service_impact": "UNKNOWN",
            "redundancy_evaluated": False, "causality_verified": False,
            "direction": "REVERSE_CONSUMER_TO_DEPENDENCY",
            "source": "db/migrations/005_seed_acme.sql",
            "provenance": "SYNTHETIC_FIXTURE", "freshness": "SYNTHETIC_CLOCK_ONLY",
            "observed_at": None, "known_at": None, "tenant_scope": "UNKNOWN"}


def _event(key, seed, idx, offset, action, ci, payload, frequency, maintenance,
           variant="CANONICAL"):
    # Namespace fixture-only identities by replay mode; default Golden stays identical.
    event_parts = [key, seed, idx, offset, action, ci]
    bucket = offset // frequency
    dedupe_parts = [key, seed, action, ci, bucket]
    corr_parts = ["ACME-LOCAL-ONLY", key, seed]
    if variant != "CANONICAL":
        event_parts.append(variant)
        dedupe_parts.append(variant)
        corr_parts.append(variant)
    unique = hashlib.sha256(_canonical(event_parts)).hexdigest()[:20].upper()
    dedupe = hashlib.sha256(_canonical(dedupe_parts)).hexdigest()[:20].upper()
    corr = hashlib.sha256(_canonical(corr_parts)).hexdigest()[:20].upper()
    active = bool(maintenance and maintenance["start_offset_seconds"] <= offset < maintenance["end_offset_seconds"])
    return {"source": SOURCE, "source_event_id": "SYN-EVT-" + unique,
            "event_time": _stamp(offset), "observed_at": _stamp(offset),
            "known_at": _stamp(offset + 1), "freshness": "SYNTHETIC_CLOCK_ONLY",
            "provenance": "SYNTHETIC_FIXTURE", "synthetic": True,
            "tenant_id": None, "tenant_scope": "UNKNOWN", "id_authority": "LOCAL_FIXTURE_ONLY",
            "ci_id": ci, "action": action, "payload": payload,
            "dedupe_key": "SYN-DEDUP-" + dedupe, "correlation_key": "SYN-CORR-" + corr,
            "maintenance_window_active": active, "at_seconds": offset,
            "observed_impact": "UNKNOWN", "evidence_id": None}


def replay(scenario_key="REDUNDANT_SAN_PATH_LOSS", seed=20261018,
           *, stochastic=False, false_positive=False, graph=None, catalog=None):
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be a declared 32-bit nonnegative integer")
    # Even caller-supplied parsed fixtures must match the pinned source files.
    # Otherwise an injected graph/catalog could fabricate a dependency or P1.
    pinned_graph = load_graph()
    if graph is None:
        graph = pinned_graph
    elif not _strict_fixture_equal(graph, pinned_graph):
        raise ValueError("unpinned graph override; use the reviewed SQL fixture")
    pinned_catalog, catalog_sha = load_catalog()
    if catalog is None:
        catalog = pinned_catalog
    elif not _strict_fixture_equal(catalog, pinned_catalog):
        raise ValueError("unpinned catalog override; use the reviewed catalog fixture")
    choices = [s for s in catalog["scenarios"] if s["key"] == scenario_key]
    if len(choices) != 1:
        raise ValueError("unknown scenario category")
    s = choices[0]
    if s["status"] != "SUPPORTED_BY_SEED":
        raise ValueError("BLOCKED_MISSING_CMDB_CI: " + s["blocker"])
    if scenario_key == "REDUNDANT_SAN_PATH_LOSS" and (stochastic or false_positive):
        raise ValueError("pinned golden story cannot be jittered or reclassified")
    if s["scenario_id"] is not None and s["scenario_id"] not in graph["scenario_ids"]:
        raise ValueError("scenario_id not in pinned seed")
    impact = dependency_candidates(graph, s["source_ci_id"], s["service_id"])
    if scenario_key == "REDUNDANT_SAN_PATH_LOSS":
        rows = [(offset, action, ci, payload) for _, offset, action, ci, payload in graph["steps"]]
    else:
        rng = random.Random(seed) if stochastic else None
        metric = s["metric"]
        if not isinstance(metric, str) or not metric:
            raise ValueError("supported scenario missing synthetic observation metric")
        rows = [(0, "SIGNAL_OPEN", s["source_ci_id"], {"scenario_category": scenario_key})]
        for offset in range(s["frequency_seconds"], s["duration_seconds"], s["frequency_seconds"]):
            value = s["metric_value_synthetic"]
            if rng is not None:
                value = round(value * (1 + rng.randint(-5, 5) / 100), 3)
            rows.append((offset, "OBSERVE", s["source_ci_id"],
                         {"metric": metric, "value": value, "unit": s["unit"],
                          "classification": "NORMAL_SYNTHETIC" if false_positive else "ANOMALY_SYNTHETIC"}))
        rows.append((s["duration_seconds"], "RECOVERY_CHECK_PLANNED", s["source_ci_id"],
                     {"verified": False, "resolution": "UNKNOWN"}))
    if len(rows) > 1000:
        raise ValueError("bounded replay exceeded")
    variant = ("CANONICAL" if not stochastic and not false_positive else
               f"STOCHASTIC={int(stochastic)};FALSE_POSITIVE={int(false_positive)}")
    events = [_event(scenario_key, seed, i, offset, action, ci, payload,
                     s["frequency_seconds"], s["maintenance_window"], variant)
              for i, (offset, action, ci, payload) in enumerate(rows, 1)]
    active = any(e["maintenance_window_active"] for e in events)
    priority = PRIORITY[impact["estimated_impact_level"]][s["urgency_synthetic"]]
    if false_positive or active:
        priority = "UNKNOWN"  # never escalate from maintenance/noise alone
    output = {"schema": "aiops.acme.synthetic-incident-replay.v1", "source": SOURCE,
              "scenario_category": scenario_key, "scenario_id": s["scenario_id"],
              "graph_source": catalog["source"], "graph_version": graph["graph_version"],
              "catalog_sha256": catalog_sha, "seed": seed, "stochastic": stochastic,
              "mode": "REPLAY", "synthetic": True, "provenance": "SYNTHETIC_FIXTURE",
              "observed_at": None, "known_at": None, "freshness": "SYNTHETIC_CLOCK_ONLY",
              "tenant_id": None, "tenant_scope": "UNKNOWN", "incident_id": None,
              "run_id": None, "ticket_id": None, "evidence_ids": [],
              "service_id": s["service_id"], "ci_id": s["source_ci_id"],
              "correlation_status": "OFFLINE_SYNTHETIC_ONLY",
              "impact_estimate": impact,
              "itil": {"impact_input": impact["estimated_impact_level"],
                       "urgency_input": s["urgency_synthetic"],
                       "scenario_severity": s["severity_synthetic"],
                       "priority_candidate": priority, "priority_confirmed": "UNKNOWN",
                       "priority_rule": "ACME_OFFLINE_MATRIX_V1",
                       "roles_planned": ["N1", "N2", "N3"] + (["INCIDENT_COMMANDER"] if priority == "P1" else []),
                       "roles_authenticated": False},
              "maintenance_window": s["maintenance_window"],
              "recovery": "CHECKPOINT_ONLY_NOT_VERIFIED",
              "checkpoints": [{"stage": name, "status": "NOT_EXECUTED", "id": None}
                              for name in CHECKPOINTS],
              "publishable_to_core_or_glpi": False,
              "live_effects_authorized": False, "event_count": len(events), "events": events}
    output["dataset_sha256"] = hashlib.sha256(_canonical(output)).hexdigest()
    return output



def correlate_golden_manifest_offline(manifest):
    """Verify the *entire* pinned golden replay before local correlation.

    This prevents an event list with plausible SYN-EVT IDs or a forged
    checkpoint/priority from being mistaken for the reviewed story. A matching
    manifest is still SYNTHETIC and is never an authenticated Core/GLPI proof.
    """
    if (not isinstance(manifest, dict) or
            manifest.get("scenario_category") != "REDUNDANT_SAN_PATH_LOSS" or
            manifest.get("scenario_id") != "SCN-GOLDEN-PAYMENT-P1" or
            manifest.get("stochastic") is not False or
            type(manifest.get("seed")) is not int or
            manifest.get("seed") != 20261018):
        raise ValueError("untrusted golden replay manifest")
    try:
        expected = replay(seed=manifest["seed"])
    except ValueError as exc:
        raise ValueError("untrusted golden replay manifest") from exc
    # Compare all fields, not only the self-declared dataset_sha256. Rehashing
    # a modified payload must never turn a fabricated observation into proof.
    # Python dict equality conflates True with 1 and 0 with False. Compare
    # canonical JSON bytes so forged scalar types cannot pass with the original
    # dataset checksum, even when the parsed dictionaries compare equal.
    if _canonical(manifest) != _canonical(expected):
        raise ValueError("golden replay manifest mismatch")
    return correlate_offline(manifest["events"])



def correlate_catalog_manifest_offline(manifest, *, false_positive=False):
    """Verify a complete graph-bound synthetic catalog replay before correlation.

    For non-golden categories, the caller must declare the false-positive mode
    explicitly; it is never inferred from attacker-controlled event payloads.
    Golden Payments always delegates to its canonical-seed strict validator.
    A match remains fixture-only, not an authenticated tenant or ITSM join.
    """
    if (not isinstance(manifest, dict) or
            not isinstance(manifest.get("scenario_category"), str) or
            type(manifest.get("seed")) is not int or
            type(manifest.get("stochastic")) is not bool or
            type(false_positive) is not bool):
        raise ValueError("untrusted catalog replay manifest")
    if manifest["scenario_category"] == "REDUNDANT_SAN_PATH_LOSS":
        if false_positive:
            raise ValueError("golden replay cannot be a false positive")
        return correlate_golden_manifest_offline(manifest)
    try:
        expected = replay(manifest["scenario_category"], manifest["seed"],
                          stochastic=manifest["stochastic"],
                          false_positive=false_positive)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("untrusted catalog replay manifest") from exc
    # A self-declared/recomputed dataset_sha256 is not a source attestation.
    # Type-sensitive JSON equality also rejects bool/int and int/float aliases.
    if _canonical(manifest) != _canonical(expected):
        raise ValueError("catalog replay manifest mismatch")
    return correlate_offline(manifest["events"])



def storyboard_offline(manifest, *, false_positive=False):
    """Project a strictly verified replay into a read-only SYNTHETIC demo story.

    Source-event IDs are local fixture IDs, never Core/GLPI/Evidence IDs.
    The projection adds no new observations or runtime checkpoint receipts.
    """
    correlated = correlate_catalog_manifest_offline(manifest, false_positive=false_positive)
    graph = load_graph()
    service_id = manifest["service_id"]
    business_links = [
        {"edge_id": edge_id, "business_ci_id": consumer}
        for edge_id, consumer in graph["consumers"][service_id]
        if graph["nodes"][consumer]["type"] == "BUSINESS"
    ]
    impact = manifest["impact_estimate"]
    events = manifest["events"]
    return {
        "schema": "aiops.acme.synthetic-storyboard.v1",
        "source": SOURCE, "provenance": "SYNTHETIC_FIXTURE",
        "synthetic": True, "publishable_to_core_or_glpi": False,
        "live_effects_authorized": False, "runtime_api_readback": "NOT_EXECUTED",
        "source_dataset_sha256": manifest["dataset_sha256"],
        "source_manifest_sha256": hashlib.sha256(_canonical(manifest)).hexdigest(),
        "scenario_id": manifest["scenario_id"],
        "scenario_category": manifest["scenario_category"],
        "seed": manifest["seed"], "stochastic": manifest["stochastic"],
        "graph_version": manifest["graph_version"],
        "catalog_sha256": manifest["catalog_sha256"],
        "tenant_scope": "UNKNOWN", "tenant_id": None,
        "incident_id": None, "run_id": None, "ticket_id": None,
        "evidence_ids": [], "service_id": service_id, "ci_id": manifest["ci_id"],
        "correlation_key": correlated["correlation_key"],
        "correlation_status": "OFFLINE_SYNTHETIC_ONLY",
        "twin_service_context": twin_service_context_offline(manifest, false_positive=false_positive),
        "dependency_path": {
            "node_ids": list(impact["path_node_ids"]),
            "edge_ids": list(impact["path_edge_ids"]),
            "business_links": business_links,
            "candidate_service_ids": list(impact["candidate_service_ids"]),
            "candidate_ci_count": impact["candidate_ci_count"],
            "estimated_impact_level": impact["estimated_impact_level"],
            "observed_service_impact": "UNKNOWN",
            "causality_verified": False,
            "redundancy_evaluated": False,
        },
        "itil": {
            "priority_candidate": manifest["itil"]["priority_candidate"],
            "priority_confirmed": "UNKNOWN",
            "roles_planned": list(manifest["itil"]["roles_planned"]),
            "roles_authenticated": False,
        },
        "event_count": len(events),
        "timeline": [
            {
                "step": index, "source_event_id": event["source_event_id"],
                "event_time": event["event_time"], "observed_at": event["observed_at"],
                "known_at": event["known_at"], "freshness": "SYNTHETIC_CLOCK_ONLY",
                "ci_id": event["ci_id"], "action": event["action"],
                "payload": dict(event["payload"]),
                "dedupe_key": event["dedupe_key"], "correlation_key": event["correlation_key"],
                "maintenance_window_active": event["maintenance_window_active"],
                "source": event["source"], "provenance": "SYNTHETIC_FIXTURE",
                "tenant_scope": "UNKNOWN",
                "runtime_evidence_id": None, "runtime_readback": "NOT_EXECUTED",
            }
            for index, event in enumerate(events, 1)
        ],
        "checkpoints": [
            {"stage": checkpoint["stage"], "status": "NOT_EXECUTED", "id": None}
            for checkpoint in manifest["checkpoints"]
        ],
        "recovery_verified": False,
    }


def twin_service_context_offline(manifest, *, false_positive=False):
    """Sourced Twin-only context; no invented owner, SLA, change or DC identity.

    The pinned 005 SQL proves only synthetic node site/criticality and edges.
    The replay must first pass the full strict manifest check. The returned
    metadata is an offline *candidate* projection, never runtime evidence.
    """
    correlate_catalog_manifest_offline(manifest, false_positive=false_positive)
    graph = load_graph()
    raw = SEED_FILE.read_bytes()
    if _git_blob(raw) != SEED_GIT_BLOB:
        raise ValueError("untrusted Twin node provenance")
    node_pattern = re.compile(
        r"^\('(ACME-[^']+)','(BUSINESS|SERVICE|APPLICATION|VM|SERVER|STORAGE|SAN|NETWORK|NAS)','[^']+','([^']+)','[^']+',([1-5]),",
        re.M,
    )
    rows = node_pattern.findall(raw.decode("utf-8"))
    details = {ci: {"type": kind, "site": site, "criticality": int(criticality)}
               for ci, kind, site, criticality in rows}
    if (len(rows) != len(graph["nodes"]) or len(details) != len(graph["nodes"]) or
            any(ci not in details or details[ci]["type"] != node["type"] or
                details[ci]["criticality"] != node["criticality"]
                for ci, node in graph["nodes"].items())):
        raise ValueError("ambiguous pinned Twin node metadata")
    impact = manifest["impact_estimate"]
    path_nodes = impact["path_node_ids"]
    service = manifest["service_id"]
    if (service not in details or details[service]["type"] != "SERVICE" or
            not path_nodes or path_nodes[-1] != service):
        raise ValueError("untrusted Twin service path")
    path_sites = {ci: details[ci]["site"] for ci in path_nodes}
    sites = set(path_sites.values())
    context = {
        "source": "db/migrations/005_seed_acme.sql",
        "source_git_blob": SEED_GIT_BLOB,
        "provenance": "SYNTHETIC_FIXTURE",
        "freshness": "PINNED_FIXTURE_NOT_LIVE",
        "tenant_scope": "UNKNOWN",
        "site": next(iter(sites)) if len(sites) == 1 else "UNKNOWN",
        "site_by_path_ci_id": path_sites,
        "datacenter_id": "UNKNOWN",
        "datacenter_relation": "UNKNOWN",
        "service_id": service,
        "service_criticality_synthetic_1_to_5": details[service]["criticality"],
        "service_owner_id": "UNKNOWN",
        "service_team_id": "UNKNOWN",
        "sla_id": "UNKNOWN",
        "ola_id": "UNKNOWN",
        "change_id": "UNKNOWN",
        "change_lookup": ("PLANNED_NOT_EXECUTED" if any(
            e["action"] == "CHANGE_LOOKUP" for e in manifest["events"])
            else "NOT_PRESENT_IN_SCENARIO"),
        "maintenance_window_synthetic": manifest["maintenance_window"],
        "maintenance_actual": "UNKNOWN",
        "dependency_direction": impact["direction"],
        "dependency_path_node_ids": list(path_nodes),
        "dependency_path_edge_ids": list(impact["path_edge_ids"]),
        "blast_radius_candidate_ci_count": impact["candidate_ci_count"],
        "blast_radius_candidate_service_ids": list(impact["candidate_service_ids"]),
        "blast_radius_observed": "UNKNOWN",
        "causality_verified": False,
        "redundancy_evaluated": False,
        "impact_estimated": impact["estimated_impact_level"],
        "impact_observed": "UNKNOWN",
        "itil_priority_candidate": manifest["itil"]["priority_candidate"],
        "itil_priority_confirmed": "UNKNOWN",
        "urgency_synthetic": manifest["itil"]["urgency_input"],
        "runtime_readback": "NOT_EXECUTED",
    }
    index = load_governance_source_index()
    catalog, _ = load_catalog()
    scenario = next(s for s in catalog["scenarios"]
                    if s["key"] == manifest["scenario_category"])
    if context["maintenance_window_synthetic"] != scenario["maintenance_window"]:
        raise ValueError("maintenance source is not the pinned scenario")
    planned_change = any(action == "CHANGE_LOOKUP"
                         for _, _, action, _, _ in graph["steps"]) if (
                             manifest["scenario_id"] == "SCN-GOLDEN-PAYMENT-P1") else False
    if (context["change_lookup"] == "PLANNED_NOT_EXECUTED") != planned_change:
        raise ValueError("change lookup is not a pinned planned step")
    records = {}
    for field, source_ref in index["fields"].items():
        value = context[field]
        if source_ref["authority"] == "UNKNOWN" and value != "UNKNOWN":
            raise ValueError("missing governance authority cannot supply a value")
        ci_ids = (
            list(path_nodes) if field == "site" else
            [service] if field == "service_criticality_synthetic_1_to_5" else
            [manifest["ci_id"]] + list(impact["candidate_service_ids"])
            if field == "blast_radius_candidate_service_ids" else []
        )
        records[field] = {
            "value": value, "authority": source_ref["authority"],
            "source": source_ref["source"], "selector": source_ref["selector"],
            "source_git_blob": (
                CATALOG_GIT_BLOB if source_ref["source"] == str(CATALOG_FILE.relative_to(ROOT))
                else SEED_GIT_BLOB if source_ref["source"] == str(SEED_FILE.relative_to(ROOT))
                else None),
            "source_ci_ids": ci_ids,
            "scenario_category": manifest["scenario_category"] if field in (
                "maintenance_window_synthetic", "change_lookup") else None,
            "provenance": "SYNTHETIC_FIXTURE",
            "tenant_scope": "UNKNOWN",
        }
    context["governance_source_index_git_blob"] = GOVERNANCE_SOURCE_GIT_BLOB
    context["governance_source_records"] = records
    return context



def load_vertical_contract_fixture(path=None):
    """Pinned script plan only. It cannot attest a lifecycle transition."""
    path = VERTICAL_CONTRACT_FILE if path is None else path
    raw = Path(path).read_bytes()
    if _git_blob(raw) != VERTICAL_CONTRACT_GIT_BLOB:
        raise ValueError("vertical contract Git blob mismatch")
    data = json.loads(raw, object_pairs_hook=_unique_object)
    if (data.get("schema") != "aiops.acme.synthetic-vertical-contract.v1" or
            data.get("provenance") != "SYNTHETIC_FIXTURE" or
            data.get("authority") != "OFFLINE_SCRIPT_ONLY" or
            data.get("scenario_id") != "SCN-GOLDEN-PAYMENT-P1" or
            type(data.get("seed")) is not int or data["seed"] != 20261018 or
            data.get("graph_git_blob") != SEED_GIT_BLOB or
            data.get("governance_index_git_blob") != GOVERNANCE_SOURCE_GIT_BLOB or
            data.get("source") != str(SEED_FILE.relative_to(ROOT)) or
            data.get("source_selector") != "scenario_steps" or
            data.get("tenant_scope") != "UNKNOWN" or
            data.get("runtime_readback") != "NOT_EXECUTED" or
            data.get("execution_status") != "NOT_EXECUTED" or
            data.get("live_effects_authorized") is not False):
        raise ValueError("vertical contract source or authority mismatch")
    stages = data.get("stages")
    if not isinstance(stages, list) or len(stages) != 15:
        raise ValueError("vertical contract must declare fifteen planned stages")
    names = [row.get("stage") for row in stages if isinstance(row, dict)]
    if len(names) != 15 or len(set(names)) != 15:
        raise ValueError("invalid vertical stage identities")
    graph = load_graph()
    steps = {n: action for n, _, action, _, _ in graph["steps"]}
    for row in stages:
        n = row.get("source_step")
        cp = row.get("runtime_checkpoint")
        if (set(row) != {"stage", "itil_practice", "source_step",
                         "expected_action", "runtime_checkpoint"} or
                type(n) is not int or n not in steps or
                row.get("expected_action") != steps[n] or
                not isinstance(row.get("itil_practice"), str) or
                not row["itil_practice"] or
                cp is not None and cp not in CHECKPOINTS):
            raise ValueError("vertical stage not backed by pinned scenario")
    return data


def vertical_contract_offline(manifest, *, fixture=None):
    """Project a fully verified Golden replay into an UNEXECUTED ITIL plan.

    Script-event anchors are not Analyst/Critic outputs, Evidence receipts,
    GLPI tickets, Core Incidents/Runs, HITL decisions or simulated executions.
    No runtime identity, SLA/OLA, Change or observed impact can be inferred.
    """
    story = storyboard_offline(manifest)  # strict canonical replay + source index
    if (story["scenario_id"] != "SCN-GOLDEN-PAYMENT-P1" or
            type(story["seed"]) is not int or story["seed"] != 20261018 or
            story["graph_version"] != SEED_GIT_BLOB):
        raise ValueError("vertical contract requires canonical Golden replay")
    pinned = load_vertical_contract_fixture()
    if fixture is None:
        fixture = pinned
    elif _canonical(fixture) != _canonical(pinned):
        raise ValueError("untrusted vertical contract override")
    timeline = story["timeline"]
    if len(timeline) != 7:
        raise ValueError("untrusted vertical contract timeline")
    stages = []
    for row in fixture["stages"]:
        event = timeline[row["source_step"] - 1]
        if event["action"] != row["expected_action"]:
            raise ValueError("vertical contract source event mismatch")
        stages.append({
            "stage": row["stage"], "itil_practice": row["itil_practice"],
            "status": "NOT_EXECUTED", "runtime_id": None,
            "runtime_evidence_ids": [], "runtime_checkpoint": row["runtime_checkpoint"],
            "source_event_id": event["source_event_id"],
            "source_event_time": event["event_time"],
            "source_event_ci_id": event["ci_id"],
            "source_action": event["action"], "source_step": row["source_step"],
            "source_authority": "OFFLINE_SCRIPT_ONLY",
            "anchor_is_runtime_proof": False,
            "tenant_scope": "UNKNOWN", "provenance": "SYNTHETIC_FIXTURE",
        })
    context = story["twin_service_context"]
    return {
        "schema": "aiops.acme.synthetic-vertical-projection.v1",
        "synthetic": True, "provenance": "SYNTHETIC_FIXTURE",
        "source": SOURCE, "source_dataset_sha256": story["source_dataset_sha256"],
        "source_manifest_sha256": story["source_manifest_sha256"],
        "source_event_ids": [e["source_event_id"] for e in timeline],
        "scenario_id": story["scenario_id"], "seed": story["seed"],
        "graph_version": story["graph_version"],
        "governance_index_git_blob": GOVERNANCE_SOURCE_GIT_BLOB,
        "contract_fixture_git_blob": VERTICAL_CONTRACT_GIT_BLOB,
        "event_count": story["event_count"],
        "tenant_scope": "UNKNOWN", "tenant_id": None,
        "ticket_id": None, "incident_id": None, "run_id": None,
        "evidence_ids": [], "runtime_readback": "NOT_EXECUTED",
        "correlation_status": "OFFLINE_SYNTHETIC_ONLY",
        "service_id": story["service_id"], "ci_id": story["ci_id"],
        "dependency_path": story["dependency_path"],
        "governance_source_records": context["governance_source_records"],
        "governance_unknowns": {
            field: context[field] for field in (
                "datacenter_id", "datacenter_relation", "service_owner_id",
                "service_team_id", "sla_id", "ola_id", "change_id",
                "maintenance_actual")
        },
        "itil": story["itil"], "observed_impact": "UNKNOWN",
        "analyst_hypothesis": "UNKNOWN", "critic_disposition": "UNKNOWN",
        "policy_decision": "UNKNOWN", "hitl_approval": "UNKNOWN",
        "simulation_executed": False, "post_action_verified": False,
        "resolution_verified": False, "reopen_verified": False,
        "checkpoints": story["checkpoints"], "stages": stages,
        "publishable_to_core_or_glpi": False, "live_effects_authorized": False,
    }



def load_event_impact_contract_fixture(path=None):
    """Pin Golden event/dedupe/correlation identities to reviewed fixture bytes.

    A synthetic source_event_id is not an ITSM Incident, Core Run or Evidence ID.
    The fixture cannot supply tenant authority, a real observation or a receipt.
    """
    path = EVENT_IMPACT_CONTRACT_FILE if path is None else path
    raw = Path(path).read_bytes()
    if _git_blob(raw) != EVENT_IMPACT_CONTRACT_GIT_BLOB:
        raise ValueError("event impact contract Git blob mismatch")
    data = json.loads(raw, object_pairs_hook=_unique_object)
    expected_keys = {
        "schema", "provenance", "authority", "scenario_id", "scenario_category",
        "seed", "graph_git_blob", "governance_index_git_blob",
        "vertical_contract_git_blob", "source_dataset_sha256", "tenant_scope",
        "correlation_key", "events", "blast_radius_candidate",
    }
    if (not isinstance(data, dict) or set(data) != expected_keys or
            data["schema"] != "aiops.acme.synthetic-event-impact-contract.v1" or
            data["provenance"] != "SYNTHETIC_FIXTURE" or
            data["authority"] != "OFFLINE_SCRIPT_ONLY" or
            data["scenario_id"] != "SCN-GOLDEN-PAYMENT-P1" or
            data["scenario_category"] != "REDUNDANT_SAN_PATH_LOSS" or
            type(data["seed"]) is not int or data["seed"] != 20261018 or
            data["graph_git_blob"] != SEED_GIT_BLOB or
            data["governance_index_git_blob"] != GOVERNANCE_SOURCE_GIT_BLOB or
            data["vertical_contract_git_blob"] != VERTICAL_CONTRACT_GIT_BLOB or
            data["tenant_scope"] != "UNKNOWN"):
        raise ValueError("event impact contract provenance or identity mismatch")
    load_governance_source_index()
    load_vertical_contract_fixture()
    golden = replay(seed=20261018)
    expected_events = [
        {"step": step, "source_event_id": event["source_event_id"],
         "offset_seconds": event["at_seconds"], "event_time": event["event_time"],
         "action": event["action"], "ci_id": event["ci_id"],
         "dedupe_key": event["dedupe_key"]}
        for step, event in enumerate(golden["events"], 1)
    ]
    impact = golden["impact_estimate"]
    expected_blast = {
        "source_ci_id": golden["ci_id"],
        "selected_service_id": golden["service_id"],
        "candidate_service_ids": impact["candidate_service_ids"],
        "candidate_ci_count": impact["candidate_ci_count"],
        "path_edge_ids": impact["path_edge_ids"],
        "path_node_ids": impact["path_node_ids"],
        "estimated_impact_level": impact["estimated_impact_level"],
        "observed_service_impact": "UNKNOWN",
    }
    if (data["source_dataset_sha256"] != golden["dataset_sha256"] or
            data["correlation_key"] != golden["events"][0]["correlation_key"] or
            _canonical(data["events"]) != _canonical(expected_events) or
            _canonical(data["blast_radius_candidate"]) != _canonical(expected_blast) or
            len({e["source_event_id"] for e in expected_events}) != 7 or
            len({e["dedupe_key"] for e in expected_events}) != 7):
        raise ValueError("event impact contract not backed by pinned Golden source")
    return data


def event_impact_contract_offline(manifest, *, fixture=None):
    """Deterministic Event->correlation->Twin candidate impact, never runtime ITIL.

    Validates the full Golden manifest (including seed, tenant and timestamps)
    before projection. The correlation group is fixture-local, not a ticket.
    """
    correlated = correlate_golden_manifest_offline(manifest)
    vertical = vertical_contract_offline(manifest)
    pinned = load_event_impact_contract_fixture()
    if fixture is None:
        fixture = pinned
    elif _canonical(fixture) != _canonical(pinned):
        raise ValueError("untrusted event impact contract override")
    events = manifest["events"]
    if (len(events) != 7 or correlated["event_count"] != 7 or
            correlated["correlation_key"] != fixture["correlation_key"]):
        raise ValueError("event impact correlation mismatch")
    timeline = []
    for expected, event in zip(fixture["events"], events):
        if (event["source_event_id"] != expected["source_event_id"] or
                event["dedupe_key"] != expected["dedupe_key"] or
                event["correlation_key"] != fixture["correlation_key"] or
                event["event_time"] != _stamp(expected["offset_seconds"]) or
                event["known_at"] != _stamp(expected["offset_seconds"] + 1) or
                event["observed_at"] != event["event_time"] or
                event["at_seconds"] != expected["offset_seconds"] or
                event["ci_id"] != expected["ci_id"] or
                event["action"] != expected["action"]):
            raise ValueError("untrusted event impact chronology or source")
        timeline.append({
            "step": expected["step"], "source_event_id": event["source_event_id"],
            "event_time": event["event_time"], "known_at": event["known_at"],
            "ci_id": event["ci_id"], "action": event["action"],
            "dedupe_key": event["dedupe_key"],
            "correlation_key": event["correlation_key"],
            "source": SOURCE, "provenance": "SYNTHETIC_FIXTURE",
            "tenant_scope": "UNKNOWN", "runtime_incident_id": None,
            "runtime_evidence_id": None, "runtime_readback": "NOT_EXECUTED",
        })
    impact = dependency_candidates(load_graph(), manifest["ci_id"], manifest["service_id"])
    expected_impact = fixture["blast_radius_candidate"]
    if (_canonical(impact["candidate_service_ids"]) !=
            _canonical(expected_impact["candidate_service_ids"]) or
            impact["candidate_ci_count"] != expected_impact["candidate_ci_count"] or
            _canonical(impact["path_edge_ids"]) !=
            _canonical(expected_impact["path_edge_ids"]) or
            _canonical(impact["path_node_ids"]) !=
            _canonical(expected_impact["path_node_ids"]) or
            impact["estimated_impact_level"] != expected_impact["estimated_impact_level"]):
        raise ValueError("untrusted Twin reverse-reachable blast radius")
    return {
        "schema": "aiops.acme.synthetic-event-impact-projection.v1",
        "synthetic": True, "provenance": "SYNTHETIC_FIXTURE",
        "authority": "OFFLINE_SCRIPT_ONLY",
        "scenario_id": manifest["scenario_id"], "seed": manifest["seed"],
        "graph_version": SEED_GIT_BLOB,
        "contract_fixture_git_blob": EVENT_IMPACT_CONTRACT_GIT_BLOB,
        "source_dataset_sha256": manifest["dataset_sha256"],
        "source_event_ids": [e["source_event_id"] for e in events],
        "event_count": len(events), "timeline": timeline,
        "correlation": {
            "key": fixture["correlation_key"], "scope": "LOCAL_FIXTURE_ONLY",
            "event_count": correlated["event_count"],
            "ci_ids": correlated["ci_ids"],
            "dedupe_keys": [e["dedupe_key"] for e in events],
            "deduplication": "SOURCE_EVENT_ID_AND_DEDUPE_KEY_ONLY",
            "tenant_scope": "UNKNOWN", "runtime_incident_id": None,
            "runtime_readback": "NOT_EXECUTED",
        },
        "blast_radius_candidate": {
            **expected_impact, "classification": "REVERSE_REACHABLE_CANDIDATE_ONLY",
            "causality_verified": False, "redundancy_evaluated": False,
            "observed_at": None, "known_at": None,
            "source": "db/migrations/005_seed_acme.sql",
            "source_git_blob": SEED_GIT_BLOB,
        },
        "itil": {
            "priority_candidate": manifest["itil"]["priority_candidate"],
            "priority_confirmed": "UNKNOWN",
            "impact_estimated": impact["estimated_impact_level"],
            "impact_observed": "UNKNOWN",
            "urgency_synthetic": manifest["itil"]["urgency_input"],
            "roles_planned": list(manifest["itil"]["roles_planned"]),
            "roles_authenticated": False,
        },
        "service_id": manifest["service_id"], "ci_id": manifest["ci_id"],
        "tenant_scope": "UNKNOWN", "tenant_id": None,
        "ticket_id": None, "incident_id": None, "run_id": None,
        "evidence_ids": [], "analyst_receipt": None, "critic_receipt": None,
        "policy_receipt": None, "hitl_receipt": None, "simulation_receipt": None,
        "runtime_readback": "NOT_EXECUTED",
        "checkpoints": vertical["checkpoints"],
        "stages": vertical["stages"],
        "governance_unknowns": vertical["governance_unknowns"],
        "publishable_to_core_or_glpi": False, "live_effects_authorized": False,
    }


def correlate_offline(events):
    """Dedup *fixture-only* events; reject untrusted IDs, CIs and evidence.

    This is not a Core correlation or tenant-authorization API. Validation is
    deliberately fail-closed even though the output is never publishable.
    """
    if not events or any(not isinstance(e, dict) or
                         e.get("provenance") != "SYNTHETIC_FIXTURE" or
                         e.get("tenant_id") is not None or
                         e.get("tenant_scope") != "UNKNOWN" for e in events):
        raise ValueError("tenant/identity not qualified; no cross-tenant correlation")
    nodes = load_graph()["nodes"]  # pinned SQL blob, not caller-supplied CMDB
    for event in events:
        if (event.get("source") != SOURCE or event.get("synthetic") is not True or
                event.get("id_authority") != "LOCAL_FIXTURE_ONLY" or
                event.get("ci_id") not in nodes or
                event.get("evidence_id") is not None or
                event.get("observed_impact") != "UNKNOWN" or
                event.get("freshness") != "SYNTHETIC_CLOCK_ONLY" or
                not isinstance(event.get("payload"), dict) or
                not re.fullmatch(r"SYN-EVT-[0-9A-F]{20}", str(event.get("source_event_id", ""))) or
                not re.fullmatch(r"SYN-DEDUP-[0-9A-F]{20}", str(event.get("dedupe_key", ""))) or
                not re.fullmatch(r"SYN-CORR-[0-9A-F]{20}", str(event.get("correlation_key", "")))):
            raise ValueError("untrusted synthetic event identity, CI or evidence")
        if (event.get("event_time") != event.get("observed_at") or
                any(not isinstance(event.get(k), str) or
                    not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", event[k])
                    for k in ("event_time", "observed_at", "known_at")) or
                synthetic_freshness(event) != "SYNTHETIC_CLOCK_ONLY"):
            raise ValueError("stale or invalid synthetic event chronology")
    keys = {e["correlation_key"] for e in events}
    if len(keys) != 1:
        raise ValueError("unrelated scenarios must not be correlated")
    by_id = {}
    for event in events:
        eid = event["source_event_id"]
        if eid in by_id and by_id[eid] != event:
            raise ValueError("conflicting source event identity")
        by_id[eid] = event
    return {"correlation_key": next(iter(keys)), "event_count": len(by_id),
            "ci_ids": sorted({e["ci_id"] for e in by_id.values()}),
            "tenant_scope": "UNKNOWN", "publishable": False,
            "provenance": "SYNTHETIC_FIXTURE"}


def synthetic_freshness(event, max_lag_seconds=300):
    """Check only simulated known-observed lag; never certify wall-clock freshness."""
    if (event.get("provenance") != "SYNTHETIC_FIXTURE" or
            event.get("tenant_scope") != "UNKNOWN"):
        return "UNKNOWN"
    try:
        known = datetime.fromisoformat(event["known_at"].replace("Z", "+00:00"))
        observed = datetime.fromisoformat(event["observed_at"].replace("Z", "+00:00"))
        delta = (known - observed).total_seconds()
        return "STALE_SYNTHETIC" if delta < 0 or delta > max_lag_seconds else "SYNTHETIC_CLOCK_ONLY"
    except (ValueError, TypeError, KeyError):
        return "UNKNOWN"


def _safe_output_path(path):
    """Never overwrite tracked source or a symlink/hardlink alias with replay JSON."""
    path = path.expanduser()
    if path.is_symlink():
        raise ValueError("refusing symlink replay output")
    if path.exists() and path.stat().st_nlink > 1:
        raise ValueError("refusing hardlinked replay output")
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError("refusing replay output inside source checkout")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="REDUNDANT_SAN_PATH_LOSS")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--stochastic", action="store_true")
    parser.add_argument("--false-positive", action="store_true")
    parser.add_argument("--vertical-contract", action="store_true",
                        help="export no-effect SYNTHETIC ITIL lifecycle contract")
    parser.add_argument("--event-impact-contract", action="store_true",
                        help="export pinned no-effect event/correlation/Twin impact contract")
    parser.add_argument("--storyboard", action="store_true",
                        help="export strict read-only SYNTHETIC timeline, not Core Evidence")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.stochastic and args.seed is None:
        parser.error("--stochastic requires explicit --seed")
    if sum((args.storyboard, args.vertical_contract, args.event_impact_contract)) > 1:
        parser.error("--storyboard, --vertical-contract and --event-impact-contract are exclusive")
    try:
        result = replay(args.scenario, 20261018 if args.seed is None else args.seed, stochastic=args.stochastic,
                        false_positive=args.false_positive)
        if args.storyboard:
            result = storyboard_offline(result, false_positive=args.false_positive)
        if args.vertical_contract:
            result = vertical_contract_offline(result)
        if args.event_impact_contract:
            result = event_impact_contract_offline(result)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    data = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    if args.output is not None:
        try:
            _safe_output_path(args.output).write_text(data, encoding="utf-8")
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
        print(json.dumps({"output": str(args.output), "sha256": hashlib.sha256(data.encode()).hexdigest(),
                          "events": result["event_count"], "synthetic": True}, sort_keys=True))
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
