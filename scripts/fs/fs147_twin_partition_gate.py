"""Read-only SAN/FS147 graph partition gate. No database or runtime mutations.

Input is a JSON capture of GET /api/twin/graph and the two RUN fact responses.
Use a capture from a qualified isolated candidate; do not treat fixture PASS as E2E.
"""
import argparse
import json
from pathlib import Path


class IsolationError(ValueError):
    pass


def qualify(graph, fs_facts, san_facts, fs_namespace, san_namespace):
    """Fail closed on ambiguous ownership, shared IDs and cross-scope edges."""
    if not fs_namespace or not san_namespace or fs_namespace == san_namespace:
        raise IsolationError("distinct nonempty namespaces required")
    nodes = graph["nodes"]
    edges = graph["edges"]
    ids = [n["node_id"] for n in nodes]
    if len(ids) != len(set(ids)):
        raise IsolationError("duplicate topology node IDs")
    if not nodes:
        raise IsolationError("empty topology capture")
    owners = {}
    for n in nodes:
        owner = n.get("namespace")
        if owner not in (fs_namespace, san_namespace):
            raise IsolationError("unscoped or unknown topology node")
        owners[n["node_id"]] = owner
    if fs_namespace not in owners.values() or san_namespace not in owners.values():
        raise IsolationError("missing topology partition")
    edge_ids = [e["edge_id"] for e in edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise IsolationError("duplicate dependency IDs")
    for edge in edges:
        a, b = edge["source_id"], edge["target_id"]
        if a not in owners or b not in owners or owners[a] != owners[b]:
            raise IsolationError("orphan or cross-namespace dependency")
    run_ids = [fs_facts["run_id"], san_facts["run_id"]]
    if not all(run_ids) or len(set(run_ids)) != 2:
        raise IsolationError("RUN IDs missing or shared")
    seen = set()
    for response, namespace in ((fs_facts, fs_namespace), (san_facts, san_namespace)):
        if response.get("synthetic") is not True:
            raise IsolationError("unmarked scenario response")
        if not response["facts"]:
            raise IsolationError("empty RUN evidence is not proof of isolation")
        for fact in response["facts"]:
            if fact["fact_id"] in seen:
                raise IsolationError("fact ID reused across RUNs")
            seen.add(fact["fact_id"])
            node_id = fact["node_id"]
            if owners.get(node_id) != namespace:
                raise IsolationError("cross-namespace observation")
            raw = fact["value"]
            payload = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(payload, dict):
                raise IsolationError("invalid fact provenance")
            if payload.get("run_id") != response["run_id"]:
                raise IsolationError("cross-RUN observation")
            if payload.get("synthetic") not in (True, "true") or payload.get("synthetic") == 1:
                raise IsolationError("unmarked observation")
            if payload.get("target_node_id") != node_id:
                raise IsolationError("missing or mismatched target provenance")
    return {"status": "PASS", "fs_run": run_ids[0], "san_run": run_ids[1],
            "nodes": len(nodes), "edges": len(edges), "facts": len(seen)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--fs-namespace", required=True)
    parser.add_argument("--san-namespace", required=True)
    args = parser.parse_args()
    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    try:
        result = qualify(capture["graph"], capture["fs_facts"],
                         capture["san_facts"], args.fs_namespace, args.san_namespace)
    except (IsolationError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "HOLD", "reason": str(exc)}))
        raise SystemExit(1) from exc
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
