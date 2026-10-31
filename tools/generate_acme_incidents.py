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


def _event(key, seed, idx, offset, action, ci, payload, frequency, maintenance):
    unique = hashlib.sha256(_canonical([key, seed, idx, offset, action, ci])).hexdigest()[:20].upper()
    bucket = offset // frequency
    dedupe = hashlib.sha256(_canonical([key, seed, action, ci, bucket])).hexdigest()[:20].upper()
    corr = hashlib.sha256(_canonical(["ACME-LOCAL-ONLY", key, seed])).hexdigest()[:20].upper()
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
    elif graph != pinned_graph:
        raise ValueError("unpinned graph override; use the reviewed SQL fixture")
    pinned_catalog, catalog_sha = load_catalog()
    if catalog is None:
        catalog = pinned_catalog
    elif catalog != pinned_catalog:
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
    events = [_event(scenario_key, seed, i, offset, action, ci, payload,
                     s["frequency_seconds"], s["maintenance_window"])
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="REDUNDANT_SAN_PATH_LOSS")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--stochastic", action="store_true")
    parser.add_argument("--false-positive", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.stochastic and args.seed is None:
        parser.error("--stochastic requires explicit --seed")
    try:
        result = replay(args.scenario, 20261018 if args.seed is None else args.seed, stochastic=args.stochastic,
                        false_positive=args.false_positive)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    data = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    if args.output is not None:
        args.output.write_text(data, encoding="utf-8")
        print(json.dumps({"output": str(args.output), "sha256": hashlib.sha256(data.encode()).hexdigest(),
                          "events": result["event_count"], "synthetic": True}, sort_keys=True))
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
