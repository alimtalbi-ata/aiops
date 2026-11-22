"""Pure graph traversal; no database or credentials required."""
# Explicit relation semantics: unknown types are excluded, never guessed.
REVERSE_DEPENDENCIES = frozenset(("DEPENDS_ON", "RUNS_ON", "USES", "PATH", "HOSTED_ON"))
FORWARD_SIMULATION = frozenset(("SIMULATED_FC_PATH", "SIMULATED_DEPENDS_ON",
                               "SIMULATED_REPLICATION", "SIMULATED_BACKUP"))

def potential_dependents(snapshot, root):
    from collections import deque
    nodes = {n["node_id"]: n for n in snapshot["nodes"]}
    if root not in nodes:
        raise KeyError(root)
    adjacency = {}
    excluded = set()
    for e in sorted(snapshot["edges"], key=lambda e: e["edge_id"]):
        a, b, kind = e["source_id"], e["target_id"], e["relation_type"]
        if kind in REVERSE_DEPENDENCIES:
            a, b = b, a
        elif kind not in FORWARD_SIMULATION:
            excluded.add(kind)
            continue
        if a in nodes and b in nodes:
            adjacency.setdefault(a, []).append((b, e["edge_id"]))
    visited = {root}
    queue = deque([(root, [], [root])])
    results = []
    truncated = False
    while queue:
        node, edges, path = queue.popleft()
        results.append({**nodes[node], "depth": len(edges),
                        "path_node_ids": path, "path_edge_ids": edges})
        for target, edge in adjacency.get(node, []):
            if target in visited:
                continue
            if len(edges) >= 8:
                truncated = True
                continue
            visited.add(target)
            queue.append((target, edges + [edge], path + [target]))
    return {"root": root, "affected": results, "impact": "POTENTIAL_ONLY",
            "causality": "UNKNOWN", "redundancy_verified": False,
            "excluded_relation_types": sorted(excluded), "depth_limit": 8,
            "truncated": truncated, "path_selection": "one shortest path per node",
            "live_remediation_authorized": False}

