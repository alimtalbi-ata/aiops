"""Synthetic batch correlation adapter; no production RCA or host action."""
from vertical_demo import canonical, execute
from hashlib import sha256

def correlate(events):
    groups = {}
    seen = {}
    for event in events:
        projection = execute(event)
        tenant = projection["tenant"]
        key = (tenant, event["resource"])
        identity = (tenant, event["id"])
        digest = projection["twin"]["evidence"]["event_sha256"]
        if identity in seen:
            if seen[identity] != digest:
                raise ValueError("conflicting event identity")
            continue
        seen[identity] = digest
        groups.setdefault(key, []).append((event, digest))
    incidents = []
    for (tenant, resource), entries in sorted(groups.items()):
        entries.sort(key=lambda item: item[0]["id"])
        evidence = [{"event_id": event["id"], "source": event["source"],
                     "sha256": digest, **({"observation": event["observation"]} if "observation" in event else {})} for event, digest in entries]
        incidents.append({
            "id": "inc-" + sha256(canonical([tenant, resource]).encode()).hexdigest()[:16],
            "tenant": tenant, "resource": resource,
            "severity": "critical" if any(e["severity"] == "critical" for e, _ in entries) else "warning",
            "alert_count": len(entries), "evidence": evidence,
            "twin": {"resource": resource, "impact": "UNKNOWN"},
            "rca": {"status": "UNKNOWN", "reason": "Correlation is not causal evidence"},
            "policy": "DENY", "production_authorized": False})
    return {"classification": "EXPERIMENTAL_SYNTHETIC", "incidents": incidents}
