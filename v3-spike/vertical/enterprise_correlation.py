"""Read-only bounded temporal/topological candidate projection, not incident publication."""
from datetime import datetime
from collections import defaultdict,deque
from enterprise_context import digest, normalize
from ingestion_demo import ingest

VERSION="E15_TEMPORAL_TOPOLOGY_PREVIEW_V1"
def timestamp(value):
    return datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ")

def dependency_path(graph,start,end):
    # Edges point from dependent to dependency. Containment, membership and
    # shared user/app access alone do not establish technical dependency.
    edges=defaultdict(list)
    for a,b,r in graph.edges:
        if r in ("requires","depends_on","depends"):
            edges[a].append((b,a,b,r))
        elif r=="hosts":
            edges[b].append((a,a,b,r))
    pending=deque([(start,[])])
    seen={start}
    while pending:
        node,path=pending.popleft()
        if len(path)>=8: continue
        for other,a,b,r in sorted(edges[node]):
            if other in seen: continue
            step={"source_id":a,"target_id":b,"relation_type":r}
            new=path+[step]
            if other==end: return new
            seen.add(other)
            pending.append((other,new))
    return None

def compatible(a,b):
    # Explicitly disjoint app/group/user contexts must not be joined.
    return all(not(a.get(k) and b.get(k) and a[k]!=b[k]) for k in ("application_id","group_id","user_id"))

def preview(records,graph,window_seconds=120):
    if type(window_seconds) is not int or not 1<=window_seconds<=3600:
        raise ValueError("invalid bounded window")
    normalized=ingest(records)
    partitions=defaultdict(list)
    undated=[]
    for incident in normalized["incidents"]:
        root=incident["resource"]
        graph.scope(root)
        for event in incident["evidence"]:
            scope=event.get("enterprise")
            if scope is None:
                undated.append({"event_id":event["event_id"],"resource":root,"sha256":event["sha256"],
                                "state":"TIMESTAMP_UNAVAILABLE"})
                continue
            kind=event["source"].split(":",1)[0]
            graph.validate_signal(root,normalize(scope,kind))
            key=(root,*(scope.get(k,"") for k in ("asset_id","application_id","group_id","user_id")))
            partitions[key].append(event)
    groups=[]
    for key,events in sorted(partitions.items()):
        root,*ids=key
        scope={k:v for k,v in zip(("asset_id","application_id","group_id","user_id"),ids) if v}
        events.sort(key=lambda e:(e["enterprise"]["occurred_at"],e["event_id"]))
        chunks=[]
        for event in events:
            at=event["enterprise"]["occurred_at"]
            if not chunks or (timestamp(at)-timestamp(chunks[-1][0]["enterprise"]["occurred_at"])).total_seconds()>window_seconds:
                chunks.append([])
            chunks[-1].append(event)
        for chunk in chunks:
            refs=[{"event_id":e["event_id"],"sha256":e["sha256"],"source":e["source"],
                   "occurred_at":e["enterprise"]["occurred_at"]} for e in chunk]
            group={"resource":root,"scope":scope,"first_at":refs[0]["occurred_at"],"last_at":refs[-1]["occurred_at"],
                   "event_count":len(refs),"distinct_source_labels":len({e["source"] for e in refs}),
                   "independent_sources_verified":False,"signals":refs}
            groups.append({"candidate_group_id":"TC-"+digest([VERSION,window_seconds,group])[:24],**group})
    groups.sort(key=lambda g:(g["first_at"],g["resource"],g["candidate_group_id"]))
    candidates=[]
    for i,a in enumerate(groups):
        for b in groups[i+1:]:
            if a["resource"]==b["resource"] or not compatible(a["scope"],b["scope"]): continue
            gap=max(0,int((timestamp(b["first_at"])-timestamp(a["last_at"])).total_seconds()))
            if gap>window_seconds: continue
            for dependent,dependency in ((a,b),(b,a)):
                path=dependency_path(graph,dependent["resource"],dependency["resource"])
                if path:
                    candidates.append({"dependent_group_id":dependent["candidate_group_id"],"dependency_group_id":dependency["candidate_group_id"],
                                       "dependent_resource":dependent["resource"],"dependency_resource":dependency["resource"],
                                       "gap_seconds":gap,"path":path,"relationship":"TEMPORAL_DEPENDENCY_CANDIDATE_NOT_CAUSAL_PROOF"})
    candidates.sort(key=lambda c:(c["gap_seconds"],c["dependent_group_id"],c["dependency_group_id"]))
    return {"classification":"SYNTHETIC_TEMPORAL_CORRELATION_PREVIEW","version":VERSION,
            "window_seconds":window_seconds,"tenant":"synthetic-demo",
            "graph_sha256":digest({"nodes":sorted(graph.nodes.values(),key=lambda n:n["node_id"]),"edges":sorted(graph.edges)}),
            "received":normalized["ingestion"]["received"],"unique":normalized["ingestion"]["unique"],
            "groups":groups,"undated":sorted(undated,key=lambda e:(e["resource"],e["event_id"])),
            "candidate_count":len(candidates),"candidates":candidates[:100],"candidates_truncated":len(candidates)>100,
            "causality_established":False,"incidents_created":False,"production_authorized":False,"operational_decision":"DENY"}
