"""Pure traversal of an already authorized graph; never fetches or grants access."""
from collections import deque

def dependencies(nodes, edges, root, *, direction="outgoing", max_depth=8):
    if direction not in ("outgoing", "incoming") or type(max_depth) is not int or not 0 <= max_depth <= 8:
        raise ValueError("invalid traversal")
    if len(nodes) > 10000 or len(edges) > 50000:
        raise ValueError("graph exceeds bound")
    ids = set()
    for node in nodes:
        key = node["node_id"]
        if not isinstance(key, str) or not key or key in ids:
            raise ValueError("invalid node identity")
        ids.add(key)
    if root not in ids:
        raise ValueError("unknown root")
    adjacent = {key: set() for key in ids}
    for edge in edges:
        source, target = edge["source_id"], edge["target_id"]
        if source not in ids or target not in ids:
            raise ValueError("dangling edge")
        if direction == "incoming":
            source, target = target, source
        adjacent[source].add(target)
    depths = {root: 0}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        if depths[current] == max_depth:
            continue
        for target in sorted(adjacent[current]):
            if target not in depths:
                depths[target] = depths[current] + 1
                queue.append(target)
    return {"root": root, "direction": direction, "max_depth": max_depth,
            "classification": "STRUCTURAL_REACHABILITY_NOT_OBSERVED_IMPACT",
            "affected": [{"node_id": key, "depth": depth} for key, depth in depths.items()]}
