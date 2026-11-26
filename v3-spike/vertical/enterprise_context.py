"""Synthetic E1 graph scope; no tenant ACL, causal inference or operational action."""
from datetime import datetime, timezone
import hashlib
import json
import re
import math

P = "NODE-CI-ENT-"
ROOT = "NODE-CI-ROOT"
CHILD = "NODE-CI-CHILD"
LYON = P+"ASSET-LYO"
CAPTURE_ROOTS = frozenset((ROOT,LYON))
TECH_TYPES = {"network","compute","database","storage","identity","endpoint"}
TECH_ROOTS = frozenset(P+x for x in ("NET-PAR","NET-LYO","WAN","LINUX-PAR","WIN-LYO","DB-PAY","DB-CRM","DB-HR","STORAGE-PAR","STORAGE-LYO","IDENTITY","PC-FIN-01","PC-HR-01","PC-SALES-01"))
ENTERPRISE_ROOTS = CAPTURE_ROOTS | TECH_ROOTS
TYPES = {"enterprise","site","infrastructure","asset","application","user_group","user"} | TECH_TYPES
REL = {
    "contains": {("enterprise","site"),("site","infrastructure"),("infrastructure","asset")} | {("infrastructure",t) for t in TECH_TYPES},
    "hosts": {("asset","service")},
    "depends_on": {("application","service"),("application","asset")},
    "uses": {("user_group","application"),("user","application")},
    "member_of": {("user","user_group")},
    "depends": {("service","service")},
    "requires": {("asset","compute"),("compute","network"),("network","network"),("application","database"),("database","storage"),("application","identity")},
    "uses_device": {("user","endpoint")},
}
DOCUMENTS = (
    {"id":"ENT-DOC-001","version":1,"scope":[P+"ASSET-PAR",P+"APP-PAY"],"title":"Payments latency runbook","text":"Compare HTTP latency and host observations before simulating intervention."},
    {"id":"ENT-DOC-002","version":1,"scope":[P+"APP-CRM"],"title":"CRM architecture","text":"CRM shares the Paris application service; verify CRM-specific observations."},
    {"id":"ENT-DOC-003","version":1,"scope":[P+"GROUP-FIN"],"title":"Finance user triage","text":"Distinguish a single user report from a group-wide service outage."},
    {"id":"ENT-DOC-004","version":1,"scope":[P+"APP-HR",P+"ASSET-LYO"],"title":"Independent HR portal","text":"Investigate the Lyon HR host independently of the Paris service."},
    {"id":"ENT-DOC-005","version":1,"scope":[P+"NET-PAR",P+"NET-LYO",P+"WAN"],"title":"Network dependency runbook","text":"Check local access and inter-site WAN separately; distinguish connectivity from application failures."},
    {"id":"ENT-DOC-006","version":1,"scope":[P+"LINUX-PAR",P+"WIN-LYO"],"title":"Compute operations","text":"Check runtime availability, CPU and memory; no host changes without policy approval."},
    {"id":"ENT-DOC-007","version":1,"scope":[P+"DB-PAY",P+"DB-CRM",P+"DB-HR"],"title":"Database triage","text":"Compare connection errors, query latency and pool saturation for the specific database."},
    {"id":"ENT-DOC-008","version":1,"scope":[P+"STORAGE-PAR",P+"STORAGE-LYO"],"title":"Storage triage","text":"Check capacity, I/O latency and affected databases before escalating."},
    {"id":"ENT-DOC-009","version":1,"scope":[P+"IDENTITY"],"title":"Directory incident runbook","text":"Check authentication failures across applications; distinguish shared identity outage from user credentials."},
    {"id":"ENT-DOC-010","version":1,"scope":[P+"PC-FIN-01",P+"PC-HR-01",P+"PC-SALES-01"],"title":"Individual workstation triage","text":"Validate device and user binding; do not infer group or application outage from one workstation."},
)
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()

# The measurements refer to isolated lab workloads mapped to fictional CI identities.
# A validated shape is not authentication of a collector.
TELEMETRY = {
    "process_cpu_ms": ("ms","PROCESS_TIME_DELTA","compute",1e5),
    "process_peak_rss_kib": ("KiB","LINUX_RUSAGE_MAXRSS","compute",1e9),
    "fsync_write_ms": ("ms","MONOTONIC_WRITE_FSYNC","storage",1e5),
    "fsync_write_bytes": ("bytes","EXACT_WRITE_COUNT","storage",1048576),
    "sqlite_query_ms": ("ms","MONOTONIC_SQLITE_QUERY","database",1e5),
    "sqlite_result_rows": ("rows","SQLITE_FETCH_COUNT","database",10000),
    "loopback_rtt_ms": ("ms","MONOTONIC_TCP_ECHO","network",1e5),
    "loopback_echo_bytes": ("bytes","TCP_ECHO_COUNT","network",1048576),
}

def validate_telemetry(item):
    if not isinstance(item,dict) or set(item)!={"classification","metric","unit","method","value"}:
        raise ValueError("invalid technical telemetry")
    metric=item["metric"]
    if not isinstance(metric,str) or metric not in TELEMETRY:
        raise ValueError("unknown telemetry metric")
    unit,method,_,maximum=TELEMETRY[metric]
    value=item["value"]
    if (item["classification"]!="MEASURED_ISOLATED_WORKLOAD" or item["unit"]!=unit or item["method"]!=method
        or type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=maximum
        or (unit in ("bytes","rows","KiB") and type(value) is not int)):
        raise ValueError("invalid technical measurement")
    return dict(item)

def normalize(raw, kind):
    if not isinstance(raw,dict) or not {"occurred_at","asset_id"} <= set(raw) or set(raw)-{"occurred_at","asset_id","application_id","group_id","user_id","message","measurement","telemetry"}:
        raise ValueError("invalid enterprise signal scope")
    timestamp=raw["occurred_at"]
    if not isinstance(timestamp,str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",timestamp):
        raise ValueError("UTC timestamp required")
    datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%SZ")
    for k,v in raw.items():
        if k.endswith("_id") and (not isinstance(v,str) or not re.fullmatch(r"NODE-CI-ENT-[A-Z0-9-]{1,80}",v)):
            raise ValueError("invalid enterprise identity")
    if "telemetry" in raw:
        if kind!="metric" or "measurement" in raw:
            raise ValueError("technical metric must be distinct from latency observation")
        validate_telemetry(raw["telemetry"])
    if "measurement" in raw:
        m=raw["measurement"]
        if (kind!="metric" or not isinstance(m,dict) or set(m)!={"classification","samples_ms","method"}
            or m["classification"]!="MEASURED_SYNTHETIC_LAB" or m["method"]!="HTTP_MONOTONIC_MEDIAN_5"
            or not isinstance(m["samples_ms"],list) or len(m["samples_ms"])!=5
            or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=1e9 for v in m["samples_ms"])):
            raise ValueError("invalid observed measurement metadata")
    if kind in ("log","event"):
        msg=raw.get("message")
        if not isinstance(msg,str) or not 1<=len(msg)<=256 or any(ord(c)<32 for c in msg):
            raise ValueError("bounded synthetic message required")
    elif "message" in raw:
        raise ValueError("message not allowed on metric")
    return dict(raw)

class Graph:
    def __init__(self, raw):
        self.nodes={}
        self.edges=[]
        for n in raw["nodes"]:
            nid=n["node_id"]
            if nid not in (ROOT,CHILD) and not nid.startswith(P):
                continue
            if nid in self.nodes or n["type"] not in ({"service"} if nid in (ROOT,CHILD) else TYPES):
                raise ValueError("invalid synthetic node")
            self.nodes[nid]={k:n[k] for k in ("node_id","type","name","site")}
        if not {ROOT,CHILD,P+"COMPANY"} <= self.nodes.keys() or len(self.nodes)>100:
            raise ValueError("incomplete enterprise graph")
        seen=set()
        for e in raw["edges"]:
            a,b,r=e["source_id"],e["target_id"],e["relation_type"]
            if a not in self.nodes and b not in self.nodes:
                continue
            if a not in self.nodes or b not in self.nodes or (self.nodes[a]["type"],self.nodes[b]["type"]) not in REL.get(r,set()):
                raise ValueError("foreign or invalid edge")
            key=(a,b,r)
            if key in seen:
                raise ValueError("duplicate edge")
            seen.add(key)
            self.edges.append(key)
    def forward(self, ids, rel):
        return {b for a,b,r in self.edges if a in ids and r==rel}
    def reverse(self, ids, rel):
        return {a for a,b,r in self.edges if b in ids and r==rel}
    def scope(self, root):
        if root not in ENTERPRISE_ROOTS or root not in self.nodes:
            raise ValueError("unsupported enterprise root")
        if root in CAPTURE_ROOTS:
            assets=self.reverse({root},"hosts") if root==ROOT else {root}
            services=self.forward(assets,"hosts")
            apps=self.reverse(services|assets,"depends_on")
            tech=set()
        else:
            # Only reverse dependency traversal: never fan out through shared dependencies.
            reached={root}
            for _ in range(len(self.nodes)):
                expanded=reached|self.reverse(reached,"requires")
                if expanded==reached:
                    break
                reached=expanded
            else:
                raise ValueError("dependency traversal did not converge")
            assets={root}
            tech={n for n in reached if self.nodes[n]["type"] in TECH_TYPES}
            hosts={n for n in reached if self.nodes[n]["type"]=="asset"}
            apps={n for n in reached if self.nodes[n]["type"]=="application"}|self.reverse(hosts|self.forward(hosts,"hosts"),"depends_on")
        groups={n for n in self.reverse(apps,"uses") if self.nodes[n]["type"]=="user_group"}
        users={n for n in self.reverse(apps,"uses") if self.nodes[n]["type"]=="user"} | self.reverse(groups,"member_of")
        if self.nodes[root]["type"]=="endpoint":
            users=self.reverse({root},"uses_device")
            groups=set()
            # These are accessible apps for the affected user, not app-wide outages.
            apps=self.forward(users,"uses")|self.forward(self.forward(users,"member_of"),"uses")
        # Site/infrastructure context includes hosting assets of affected applications,
        # not a claim that their hosts have failed.
        app_dependencies=self.forward(apps,"depends_on")
        app_hosts={n for n in app_dependencies if self.nodes[n]["type"]=="asset"}|self.reverse(app_dependencies,"hosts")
        infra=self.reverse(assets|tech|app_hosts,"contains")
        sites=self.reverse(infra,"contains")
        return {"assets":assets,"applications":apps,"groups":groups,"users":users,"infrastructure":infra,"sites":sites,"technical":tech,"application_hosts":app_hosts}
    def validate_signal(self, root, scope):
        allowed=self.scope(root)
        asset=scope["asset_id"]
        if "telemetry" in scope:
            item=validate_telemetry(scope["telemetry"])
            if root!=asset or self.nodes[root]["type"]!=TELEMETRY[item["metric"]][2]:
                raise ValueError("technical telemetry incompatible with asset type")
        app=scope.get("application_id")
        group=scope.get("group_id")
        user=scope.get("user_id")
        for value,k in ((asset,"assets"),(app,"applications"),(group,"groups"),(user,"users")):
            if value is not None and value not in allowed[k]:
                raise ValueError("signal outside enterprise service scope")
        if root in CAPTURE_ROOTS and app and app not in self.reverse(self.forward({asset},"hosts")|{asset},"depends_on"):
            raise ValueError("application not hosted by asset")
        if self.nodes[root]["type"]=="endpoint" and user not in allowed["users"]:
            raise ValueError("endpoint requires bound individual")
        if (group or user) and not app:
            raise ValueError("user context requires application")
        if group and app not in self.forward({group},"uses"):
            raise ValueError("group does not use application")
        if user:
            memberships=self.forward({user},"member_of")
            if group and group not in memberships:
                raise ValueError("user not in group")
            if app not in self.forward({user},"uses")|self.forward(memberships,"uses"):
                raise ValueError("user does not use application")
    def project(self, details, run):
        if details["run_id"]!=run["run_id"] or details["policy"]!="DENY" or details["production_authorized"] is not False:
            raise ValueError("unverified run")
        root=details["root"]
        allowed=self.scope(root)
        timeline=[]
        subjects=set()
        evidence={e["evidence_id"]:e["payload_hash"] for e in details["evidence"]}
        scoped=set()
        for row in details["verified_signals"]:
            eid=row["evidence_id"]
            if evidence.get(eid)!=row["payload_hash"]:
                raise ValueError("unbound signal")
            signal=row["signal"]
            entry={"evidence_id":eid,"payload_hash":row["payload_hash"],"source":signal["source"],"event_id":signal["event_id"],"resource":root}
            if "observation" in signal:
                entry["observation"]=signal["observation"]
            if "enterprise" in signal:
                scope=normalize(signal["enterprise"],signal["source"].split(":",1)[0])
                self.validate_signal(root,scope)
                entry.update(scope)
                subjects.update([scope["user_id"]] if "user_id" in scope else [])
                scoped.update(v for k,v in scope.items() if k.endswith("_id"))
            timeline.append(entry)
        timeline.sort(key=lambda e:(e.get("occurred_at",""),e["event_id"]))
        # Topological exposure is not an observed outage; even a single user report
        # must not silently become proof of a group-wide incident.
        exposed=set().union(*allowed.values())
        doc_scope=scoped or exposed
        if root in TECH_ROOTS:
            doc_scope=doc_scope|{root}
        citations=[{**d,"sha256":digest(d),"observed_evidence":False,"provenance":"SYNTHETIC_REFERENCE_ONLY"}
                   for d in DOCUMENTS if set(d["scope"]) & doc_scope]
        return {"classification":"SYNTHETIC_ENTERPRISE_CONTEXT_E1","tenant":"synthetic-demo",
                "run_id":run["run_id"],"incident_id":run["incident_id"],"root":root,
                "topology_sha256":digest({"nodes":sorted(self.nodes.values(),key=lambda n:n["node_id"]),"edges":sorted(self.edges)}),
                "exposure_semantics":"INDIVIDUAL_ACCESS_ONLY" if self.nodes[root]["type"]=="endpoint" else "TOPOLOGICAL_POTENTIAL_ONLY",
                "potential_exposure":{k:[self.nodes[n] for n in sorted(v)] for k,v in allowed.items()},
                "reported_user_ids":sorted(subjects),"timeline":timeline,"document_references":citations,
                "observed_outage_established":False,"causality_established":False,
                "tenant_acl_qualified":False,"operational_decision":"DENY","production_authorized":False}
