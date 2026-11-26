"""Synthetic E1 graph scope; no tenant ACL, causal inference or operational action."""
from datetime import datetime, timezone
import hashlib
import json
import re

P = "NODE-CI-ENT-"
ROOT = "NODE-CI-ROOT"
CHILD = "NODE-CI-CHILD"
LYON = P+"ASSET-LYO"
ENTERPRISE_ROOTS = frozenset((ROOT,LYON))
TYPES = {"enterprise","site","infrastructure","asset","application","user_group","user"}
REL = {
    "contains": {("enterprise","site"),("site","infrastructure"),("infrastructure","asset")},
    "hosts": {("asset","service")},
    "depends_on": {("application","service"),("application","asset")},
    "uses": {("user_group","application"),("user","application")},
    "member_of": {("user","user_group")},
    "depends": {("service","service")},
}
DOCUMENTS = (
    {"id":"ENT-DOC-001","version":1,"scope":[P+"ASSET-PAR",P+"APP-PAY"],"title":"Payments latency runbook","text":"Compare HTTP latency and host observations before simulating intervention."},
    {"id":"ENT-DOC-002","version":1,"scope":[P+"APP-CRM"],"title":"CRM architecture","text":"CRM shares the Paris application service; verify CRM-specific observations."},
    {"id":"ENT-DOC-003","version":1,"scope":[P+"GROUP-FIN"],"title":"Finance user triage","text":"Distinguish a single user report from a group-wide service outage."},
    {"id":"ENT-DOC-004","version":1,"scope":[P+"APP-HR",P+"ASSET-LYO"],"title":"Independent HR portal","text":"Investigate the Lyon HR host independently of the Paris service."},
)
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def normalize(raw, kind):
    if not isinstance(raw,dict) or not {"occurred_at","asset_id"} <= set(raw) or set(raw)-{"occurred_at","asset_id","application_id","group_id","user_id","message"}:
        raise ValueError("invalid enterprise signal scope")
    timestamp=raw["occurred_at"]
    if not isinstance(timestamp,str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",timestamp):
        raise ValueError("UTC timestamp required")
    datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%SZ")
    for k,v in raw.items():
        if k.endswith("_id") and (not isinstance(v,str) or not re.fullmatch(r"NODE-CI-ENT-[A-Z0-9-]{1,80}",v)):
            raise ValueError("invalid enterprise identity")
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
        assets=self.reverse({root},"hosts") if root==ROOT else {root}
        services=self.forward(assets,"hosts")
        apps=self.reverse(services|assets,"depends_on")
        groups={n for n in self.reverse(apps,"uses") if self.nodes[n]["type"]=="user_group"}
        users={n for n in self.reverse(apps,"uses") if self.nodes[n]["type"]=="user"} | self.reverse(groups,"member_of")
        infra=self.reverse(assets,"contains")
        sites=self.reverse(infra,"contains")
        return {"assets":assets,"applications":apps,"groups":groups,"users":users,"infrastructure":infra,"sites":sites}
    def validate_signal(self, root, scope):
        allowed=self.scope(root)
        asset=scope["asset_id"]
        app=scope.get("application_id")
        group=scope.get("group_id")
        user=scope.get("user_id")
        for value,k in ((asset,"assets"),(app,"applications"),(group,"groups"),(user,"users")):
            if value is not None and value not in allowed[k]:
                raise ValueError("signal outside enterprise service scope")
        if app and app not in self.reverse(self.forward({asset},"hosts")|{asset},"depends_on"):
            raise ValueError("application not hosted by asset")
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
        citations=[{**d,"sha256":digest(d),"observed_evidence":False,"provenance":"SYNTHETIC_REFERENCE_ONLY"}
                   for d in DOCUMENTS if set(d["scope"]) & doc_scope]
        return {"classification":"SYNTHETIC_ENTERPRISE_CONTEXT_E1","tenant":"synthetic-demo",
                "run_id":run["run_id"],"incident_id":run["incident_id"],"root":root,
                "topology_sha256":digest({"nodes":sorted(self.nodes.values(),key=lambda n:n["node_id"]),"edges":sorted(self.edges)}),
                "potential_exposure":{k:[self.nodes[n] for n in sorted(v)] for k,v in allowed.items()},
                "reported_user_ids":sorted(subjects),"timeline":timeline,"document_references":citations,
                "observed_outage_established":False,"causality_established":False,
                "tenant_acl_qualified":False,"operational_decision":"DENY","production_authorized":False}
