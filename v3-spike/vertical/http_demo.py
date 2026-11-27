"""Loopback-only synthetic HTTP adapter for the existing vertical demo."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from vertical_demo import execute
from correlation_demo import correlate
from core_read import read_run
from lab_context import context, dynamic_context, get
from enterprise_context import Graph, normalize, ENTERPRISE_ROOTS
from policy_demo import simulation_decision
from copilot_context import answer
import os
from hitl_demo import ApprovalGate, DurableApprovalGate
from ingestion_demo import ingest
from ingestion_store import persist
from core_ingest import create_and_persist
from mattermost_demo import command, authenticate
from glpi_demo import preview as glpi_preview

EVENT = {"id": "synthetic-001", "source": "synthetic-monitor",
         "severity": "critical", "resource": "demo-node-01",
         "tenant": "synthetic-demo"}

def enterprise_projection(graph, details, run, clock, search_query=None):
    result=graph.project(details,run)
    if clock is None:
        return result
    # Scope comes from the verified graph projection, never a caller's search filter.
    scope={v for row in result["timeline"] for k,v in row.items()
           if k in ("asset_id","application_id","group_id","user_id")}
    if not scope:
        scope={n["node_id"] for nodes in result["potential_exposure"].values() for n in nodes}
    scope.add(result["root"])
    query=" ".join(str(row.get("message",""))+" "+str(row.get("observation",{}).get("metric","")) for row in result["timeline"])[:512]
    history=clock.historical_documents(run["run_id"],scope,query if search_query is None else search_query)
    result["document_history"]={k:v for k,v in history.items() if k not in ("citations","lifecycle_citations","hybrid_retrieval","case_retrieval")}
    if history["state"]=="HISTORICAL_LOGICAL_VERSION":
        result["document_references"]=history["citations"]
        result["lifecycle_references"]=history["lifecycle_citations"]
        result["hybrid_retrieval"]=history["hybrid_retrieval"]
        result["case_retrieval"]=history["case_retrieval"]
    elif history["state"]=="PRE_E7_UNAVAILABLE":
        result["document_references"]=[]
    return result

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data, mime="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        collector_guard = getattr(self.server, 'collector_guard', None)
        if collector_guard is not None:
            from collector_http_boundary import dispatch
            if dispatch(self, **collector_guard):
                return
        if self.path == '/api/v1/mattermost/command':
            try:
                if self.headers.get('Content-Type','').split(';')[0] != 'application/x-www-form-urlencoded':
                    raise ValueError('form required')
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096:
                    raise ValueError('invalid length')
                token,channel=self.server.mattermost_config
                body=self.rfile.read(length)
                authenticate(body,token,channel)
                core=read_run(*self.server.core_config)
                twin,evidence,node,expected=self.server.context_config
                run=core['run']
                if run['incident_id']!=expected or run['mode']!='DEMO':
                    raise ValueError('binding mismatch')
                details=context(twin,evidence,run['run_id'],node)
                self.reply(200,json.dumps(command(body,token,channel,core,details)).encode())
            except Exception:
                self.reply(403,b'{"error":"CHATOPS_UNVERIFIED","policy":"DENY"}')
            return
        if self.path not in ("/api/v1/hitl/dynamic/request","/api/v1/hitl/dynamic/decide","/api/v1/hitl/request","/api/v1/hitl/decide","/api/v1/ingest","/api/v1/ingest/persist","/api/v1/ingest/create","/api/v1/ingest/admit","/api/v1/glpi/preview","/api/v1/enterprise-clock/advance","/api/v1/enterprise-clock/capture","/api/v1/enterprise-clock/capture-technical","/api/v1/enterprise-clock/capture-scenarios","/api/v1/enterprise-search","/api/v1/enterprise-parametric/configure","/api/v1/enterprise-correlation/preview","/api/v1/enterprise-correlation/historical","/api/v1/enterprise-correlation/assessment","/api/v1/enterprise-correlation/rag-context","/api/v1/ai-telemetry","/api/v1/enterprise-correlation/ai-review"):
            self.reply(404,b'{"error":"NOT_FOUND"}')
            return
        try:
            if self.headers.get("Origin") != "http://127.0.0.1:%d" % self.server.server_port:
                raise ValueError("Origin mismatch")
            if self.headers.get("Content-Type") != "application/json":
                raise ValueError("JSON required")
            length=int(self.headers.get("Content-Length","0"))
            if not 0 < length <= 4096:
                raise ValueError("Invalid length")
            data=json.loads(self.rfile.read(length))
            if self.path=="/api/v1/ai-telemetry":
                from gamma_ai_telemetry import snapshot
                if not isinstance(data,dict) or set(data)!={"run_ids"} or self.server.enterprise_clock is None:raise ValueError("invalid telemetry request")
                self.reply(200,json.dumps(snapshot(self.server.enterprise_clock,data["run_ids"])).encode())
                return
            if self.path in ("/api/v1/enterprise-correlation/historical","/api/v1/enterprise-correlation/assessment","/api/v1/enterprise-correlation/rag-context","/api/v1/enterprise-correlation/ai-review"):
                from enterprise_historical_correlation import historical_preview
                if not isinstance(data,dict) or set(data)!={"run_ids","window_seconds"}:
                    raise ValueError("invalid historical correlation request")
                if self.path.endswith("/ai-review") and self.server.ai_runtime is None:
                    raise ValueError("AI runtime disabled")
                def load_history():
                    port,token,_=self.server.core_config
                    twin,evidence,node,_=self.server.context_config
                    graph=Graph(get(twin,"/api/twin/graph"))
                    def load(rid):
                        return dynamic_context(port,token,rid,twin,evidence,node,include_signals=True,multiasset=True)
                    return historical_preview(data["run_ids"],data["window_seconds"],graph,load)
                if self.path.endswith("/ai-review"):
                    result=self.server.ai_runtime.execute(load_history)
                    self.reply(200,json.dumps(result).encode())
                    return
                result=load_history()
                if self.path.endswith("/assessment"):
                    from historical_analyst_critic import assess
                    result=assess(result)
                elif self.path.endswith("/rag-context"):
                    from historical_rag_context import build
                    if self.server.enterprise_clock is None:raise ValueError("clock not configured")
                    result=build(result,self.server.enterprise_clock)
                self.reply(200,json.dumps(result).encode())
                return
            if self.path=="/api/v1/enterprise-correlation/preview":
                from enterprise_correlation import preview
                if not isinstance(data,dict) or set(data)!={"records","window_seconds"}:
                    raise ValueError("invalid correlation preview")
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                result=preview(data["records"],graph,data["window_seconds"])
                self.reply(200,json.dumps(result).encode())
                return
            if self.path=="/api/v1/enterprise-parametric/configure":
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                result=self.server.enterprise_clock.configure_parametric(data,graph)
                self.reply(200,json.dumps(result).encode())
                return
            if self.path=="/api/v1/enterprise-search":
                if (not isinstance(data,dict) or set(data)!={"run_id","query"} or not isinstance(data["query"],str)
                    or not 1<=len(data["query"])<=512 or self.server.enterprise_clock is None):
                    raise ValueError("invalid historical search")
                port,token,_=self.server.core_config
                twin,evidence,node,_=self.server.context_config
                core,details=dynamic_context(port,token,data["run_id"],twin,evidence,node,include_signals=True,multiasset=True)
                result=enterprise_projection(Graph(get(twin,"/api/twin/graph")),details,core["run"],self.server.enterprise_clock,data["query"])
                if "hybrid_retrieval" not in result:
                    raise ValueError("historical corpus unavailable")
                self.reply(200,json.dumps({"run_id":result["run_id"],"incident_id":result["incident_id"],**result["hybrid_retrieval"],"case_retrieval":result["case_retrieval"]}).encode())
                return
            if self.path=="/api/v1/ingest":
                self.reply(200,json.dumps(ingest(data)).encode())
                return
            if self.path in ("/api/v1/enterprise-clock/advance","/api/v1/enterprise-clock/capture","/api/v1/enterprise-clock/capture-technical","/api/v1/enterprise-clock/capture-scenarios"):
                if not isinstance(data,dict) or set(data)!={"expected_tick"} or self.server.enterprise_clock is None:
                    raise ValueError("clock not configured or invalid command")
                port,token,_=self.server.core_config
                twin,evidence,node,_=self.server.context_config
                def publish(rows):
                    graph=Graph(get(twin,"/api/twin/graph"))
                    roots={row["resource"] for row in rows}
                    if len(roots)!=1 or not roots<=ENTERPRISE_ROOTS:
                        raise ValueError("unbound model resource")
                    for row in rows:
                        graph.validate_signal(row["resource"],normalize(row["enterprise"],row["kind"]))
                    return create_and_persist(rows,port,token,evidence)
                if self.path.endswith("/capture-scenarios"):
                    result=self.server.enterprise_clock.capture_scenarios(data["expected_tick"],publish)
                elif self.path.endswith("/capture-technical"):
                    if self.server.technical_collector is None:
                        raise ValueError("technical collector not configured")
                    result=self.server.enterprise_clock.capture_technical(data["expected_tick"],self.server.technical_collector,publish)
                elif self.path.endswith("/capture"):
                    if self.server.enterprise_collector is None:
                        raise ValueError("collector not configured")
                    result=self.server.enterprise_clock.capture(data["expected_tick"],self.server.enterprise_collector,publish)
                else:
                    result=self.server.enterprise_clock.advance(data["expected_tick"],publish)
                self.reply(200,json.dumps(result).encode())
                return
            if self.path=="/api/v1/ingest/admit":
                from incident_admission import admit
                port,token,_=self.server.core_config
                twin,evidence,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                admission=admit(data,graph)
                # The existing explicit manual create route is intentionally unchanged.
                # Admission creates a DEMO run only; no execution command is issued.
                result={"admission":admission,"publication":None,"production_authorized":False}
                if admission["admitted"]:
                    result["publication"]=create_and_persist(data,port,token,evidence)
                self.reply(200,json.dumps(result).encode())
                return
            if self.path=="/api/v1/ingest/create":
                port,token,_=self.server.core_config
                twin,evidence,node,_=self.server.context_config
                if isinstance(data,list) and any(isinstance(row,dict) and "enterprise" in row for row in data):
                    graph=Graph(get(twin,"/api/twin/graph"))
                    roots={row["resource"] for row in data}
                    if len(roots)!=1 or not roots<=ENTERPRISE_ROOTS:
                        raise ValueError("one verified enterprise resource per incident required")
                    for row in data:
                        if "enterprise" not in row:
                            raise ValueError("mixed or unbound enterprise signal")
                        graph.validate_signal(row["resource"],normalize(row["enterprise"],row["kind"]))
                self.reply(200,json.dumps(create_and_persist(data,port,token,evidence)).encode())
                return
            if self.path in ("/api/v1/hitl/dynamic/request","/api/v1/hitl/dynamic/decide"):
                port,token,_=self.server.core_config
                twin,evidence,node,_=self.server.context_config
                core,details=dynamic_context(port,token,data["run_id"],twin,evidence,node,multiasset=True)
                run=core["run"]
                policy=simulation_decision(self.server.policy_port,len(details["evidence"]))
                if policy["policy_decision"]!="SIMULATE" or policy["simulation_only"] is not True:
                    raise ValueError("simulation decision required")
                args=(run["incident_id"],run["run_id"],details["evidence"])
                if self.path.endswith("/request"):
                    result=self.server.approval_gate.request(*args)
                else:
                    result=self.server.approval_gate.decide(data["request_id"],*args,data.get("approved"))
                result.update(run_id=run["run_id"],incident_id=run["incident_id"],production_authorized=False)
                self.reply(200,json.dumps(result).encode())
                return
            core=read_run(*self.server.core_config)
            twin,evidence,node,expected=self.server.context_config
            run=core["run"]
            if run["incident_id"]!=expected:
                raise ValueError("Incident mismatch")
            if self.path=="/api/v1/ingest/persist":
                if run["mode"]!="DEMO":
                    raise ValueError("DEMO required")
                self.reply(200,json.dumps(persist(data,evidence,run["run_id"])).encode())
                return
            details=context(twin,evidence,run["run_id"],node)
            if self.path=="/api/v1/glpi/preview":
                if run["mode"]!="DEMO":
                    raise ValueError("DEMO required")
                self.reply(200,json.dumps(glpi_preview(data["ticket"],data["followup"],core,details)).encode())
                return
            args=(expected,run["run_id"],details["evidence"])
            if self.path.endswith("/request"):
                result=self.server.approval_gate.request(*args)
            else:
                result=self.server.approval_gate.decide(data["request_id"],*args,data.get("approved"))
            self.reply(200,json.dumps(result).encode())
        except Exception as exc:
            if isinstance(self,ContainerLabHandler):
                # The explicit disposable profile logs only the exception class
                # and a code location, never the request, message, token or body.
                import traceback
                last=traceback.extract_tb(exc.__traceback__)[-1]
                print("GAMMA_REQUEST_UNVERIFIED",type(exc).__name__,Path(last.filename).name,last.lineno,flush=True)
            self.reply(503,b'{"error":"REQUEST_UNVERIFIED","policy":"DENY"}')

    def do_GET(self):
        if self.path == "/":
            self.reply(200, Path(__file__).with_name("operator.html").read_bytes(),
                       "text/html; charset=utf-8")
        elif self.path in ("/api/v1/demo", "/api/v1/demo?simulate=1"):
            result = execute(EVENT, approved=self.path.endswith("?simulate=1"))
            self.reply(200, json.dumps(result).encode())
        elif self.path == "/api/v1/incidents":
            second = {**EVENT, "id": "synthetic-002", "source": "synthetic-log",
                      "severity": "warning"}
            self.reply(200, json.dumps(correlate([EVENT, second])).encode())
        elif self.path == "/api/v1/core-run":
            config = self.server.core_config
            if config is None:
                self.reply(503, b'{"error":"CORE_NOT_CONFIGURED","policy":"DENY"}')
                return
            try:
                result = read_run(*config)
                self.reply(200, json.dumps(result).encode())
            except Exception:
                self.reply(503, b'{"error":"CORE_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/ai-runtime/status":
            self.reply(200,json.dumps({"classification":"SYNTHETIC_GAMMA_AI_RUNTIME_STATUS_E27","enabled":self.server.ai_runtime is not None,"production_authorized":False,"operational_decision":"DENY"}).encode())
        elif self.path=="/api/v1/enterprise-inventory":
            try:
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                roots=sorted(ENTERPRISE_ROOTS & graph.nodes.keys())
                self.reply(200,json.dumps({"classification":"SYNTHETIC_ENTERPRISE_INVENTORY",
                    "nodes":sorted(graph.nodes.values(),key=lambda n:n["node_id"]),
                    "edges":[{"source_id":a,"target_id":b,"relation_type":r} for a,b,r in sorted(graph.edges)],
                    "incident_roots":roots,"production_authorized":False,"operational_decision":"DENY"}).encode())
            except Exception:
                self.reply(503,b'{"error":"INVENTORY_UNVERIFIED","policy":"DENY"}')
        elif self.path.startswith("/api/v1/enterprise-impact?root="):
            try:
                root=self.path.split("=",1)[1]
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                scope=graph.scope(root)
                self.reply(200,json.dumps({"classification":"SYNTHETIC_TOPOLOGICAL_IMPACT",
                    "root":root,"exposure_semantics":"INDIVIDUAL_ACCESS_ONLY" if graph.nodes[root]["type"]=="endpoint" else "TOPOLOGICAL_POTENTIAL_ONLY",
                    "potential_exposure":{k:[graph.nodes[n] for n in sorted(v)] for k,v in scope.items()},
                    "observed_outage_established":False,"production_authorized":False,"operational_decision":"DENY"}).encode())
            except Exception:
                self.reply(503,b'{"error":"IMPACT_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-scenarios":
            try:
                from enterprise_scenarios import describe,VERSION
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                rows=describe()
                for row in rows: graph.scope(row["resource"])
                self.reply(200,json.dumps({"classification":"SYNTHETIC_SCENARIO_CATALOG","campaign":VERSION,"scenarios":rows,"production_authorized":False,"operational_decision":"DENY"}).encode())
            except Exception:
                self.reply(503,b'{"error":"SCENARIOS_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-parametric":
            try:
                from enterprise_parametric import validate_graph
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                twin,_,_,_=self.server.context_config
                result=self.server.enterprise_clock.parametric_timeline()
                validate_graph(result["records"],Graph(get(twin,"/api/twin/graph")))
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"PARAMETRIC_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-triage":
            try:
                from enterprise_triage import validate_graph
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                result=self.server.enterprise_clock.triage_timeline()
                validate_graph(result["records"],graph)
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"TRIAGE_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-episodes":
            try:
                from enterprise_episodes import validate_graph
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                result=self.server.enterprise_clock.episode_timeline()
                validate_graph(result["records"],graph)
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"EPISODES_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-case-knowledge":
            try:
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                result=self.server.enterprise_clock.case_catalog()
                if any(not set(d["scope"])<=graph.nodes.keys() for d in result["documents"]):
                    raise ValueError("unbound case scope")
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"CASE_KNOWLEDGE_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-knowledge":
            try:
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                result=self.server.enterprise_clock.knowledge_catalog()
                if any(not set(d["scope"])<=graph.nodes.keys() for d in result["documents"]):
                    raise ValueError("unbound knowledge scope")
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"KNOWLEDGE_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-corpus":
            try:
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                result=self.server.enterprise_clock.document_catalog()
                if any(not set(d["scope"])<=graph.nodes.keys() for d in result["documents"]):
                    raise ValueError("unbound document scope")
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"CORPUS_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-activity":
            try:
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                twin,_,_,_=self.server.context_config
                graph=Graph(get(twin,"/api/twin/graph"))
                result=self.server.enterprise_clock.activity()
                for record in result["records"]:
                    graph.validate_signal(record["resource"],normalize(record["scope"],"metric"))
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"ACTIVITY_UNVERIFIED","policy":"DENY"}')
        elif self.path=="/api/v1/enterprise-clock":
            try:
                if self.server.enterprise_clock is None:
                    raise ValueError("clock not configured")
                self.reply(200,json.dumps(self.server.enterprise_clock.status()).encode())
            except Exception:
                self.reply(503,b'{"error":"CLOCK_UNVERIFIED","policy":"DENY"}')
        elif self.path.startswith("/api/v1/enterprise-context?run_id="):
            try:
                run_id=self.path.split("=",1)[1]
                port,token,_=self.server.core_config
                twin,evidence,node,_=self.server.context_config
                core,details=dynamic_context(port,token,run_id,twin,evidence,node,include_signals=True,multiasset=True)
                graph=Graph(get(twin,"/api/twin/graph"))
                result=enterprise_projection(graph,details,core["run"],self.server.enterprise_clock)
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"ENTERPRISE_CONTEXT_UNVERIFIED","policy":"DENY"}')
        elif self.path.startswith("/api/v1/e17/recovery?"):
            try:
                from urllib.parse import parse_qs,urlsplit
                from e17_readback import dynamic_recovery
                # Existing loopback-only demo, never a tenant-authorized portal.
                origin="http://127.0.0.1:%d" % self.server.server_port
                if self.headers.get("Host")!=origin.removeprefix("http://") or self.headers.get("Origin",origin)!=origin:
                    raise ValueError("foreign origin")
                params=parse_qs(urlsplit(self.path).query,strict_parsing=True,max_num_fields=2)
                if set(params)!={"original_run_id","comparison_run_id"} or any(len(v)!=1 for v in params.values()):
                    raise ValueError("two selected run IDs required")
                port,token,_=self.server.core_config
                twin,evidence,node,_=self.server.context_config
                result=dynamic_recovery(port,token,twin,evidence,node,
                    params["original_run_id"][0],params["comparison_run_id"][0])
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"E17_RECOVERY_UNVERIFIED","policy":"DENY","production_authorized":false}')
        elif self.path.startswith("/api/v1/incident-context/dynamic?run_id="):
            try:
                run_id=self.path.split("=",1)[1]
                simulate=run_id.endswith("&decision=simulate")
                if simulate:
                    run_id=run_id.removesuffix("&decision=simulate")
                port,token,_=self.server.core_config
                twin,evidence,node,_=self.server.context_config
                core,details=dynamic_context(port,token,run_id,twin,evidence,node,include_signals=True,multiasset=True)
                scoped=any("enterprise" in row["signal"] for row in details.get("verified_signals",[]))
                enterprise=enterprise_projection(Graph(get(twin,"/api/twin/graph")),details,core["run"],self.server.enterprise_clock) if scoped else None
                details.pop("verified_signals",None)
                result={"core":core,"context":details,"copilot":answer(core,details),
                    "binding":"VERIFIED_DYNAMIC_LAB_NODE","production_authorized":False}
                if enterprise is not None:
                    result["enterprise_context"]=enterprise
                    result["copilot"]["enterprise_document_retrieval"]={
                        "run_id":run_id,"topology_sha256":enterprise["topology_sha256"],
                        "citations":enterprise["document_references"],"document_history":enterprise.get("document_history"),"lifecycle_citations":enterprise.get("lifecycle_references",[]),"hybrid_retrieval":enterprise.get("hybrid_retrieval"),"case_retrieval":enterprise.get("case_retrieval"),"production_authorized":False,
                        "llm_inference_performed":False,"operational_decision":"DENY"}
                    result["copilot"]["enterprise_scope"]={
                        "root":enterprise["root"],"exposure_semantics":enterprise["exposure_semantics"],
                        "potential_application_ids":[x["node_id"] for x in enterprise["potential_exposure"]["applications"]],
                        "potential_user_ids":[x["node_id"] for x in enterprise["potential_exposure"]["users"]],
                        "reported_user_ids":enterprise["reported_user_ids"],
                        "observed_outage_established":False}
                    if enterprise["root"] in ENTERPRISE_ROOTS:
                        scope=result["copilot"]["enterprise_scope"]
                        result["copilot"]["answer"]=(f"Incident {enterprise['incident_id']}: "
                            f"{len(scope['potential_application_ids'])} potentially exposed applications or user-access contexts; "
                            f"{len(scope['potential_user_ids'])} potentially exposed users; "
                            f"{len(details['evidence'])} verified evidence records. "
                            "Root cause UNKNOWN. Operational action DENY.")
                if simulate:
                    result["simulation"]=simulation_decision(self.server.policy_port,len(details["evidence"]))
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503,b'{"error":"CONTEXT_UNVERIFIED","policy":"DENY"}')
        elif self.path in ("/api/v1/incident-context", "/api/v1/incident-context?decision=simulate"):
            try:
                core = read_run(*self.server.core_config)
                twin_port, evidence_port, node_id, expected_incident = self.server.context_config
                run = core["run"]
                if run["incident_id"] != expected_incident:
                    raise ValueError("incident binding mismatch")
                details = context(twin_port, evidence_port, run["run_id"], node_id)
                result={"core":core,"context":details,
                    "binding":"EXPLICIT_SYNTHETIC_LAB_CONFIG","production_authorized":False}
                result["copilot"]=answer(core,details)
                if self.path.endswith("?decision=simulate"):
                    result["simulation"]=simulation_decision(self.server.policy_port,len(details["evidence"]))
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503, b'{"error":"CONTEXT_UNVERIFIED","policy":"DENY"}')
        else:
            self.reply(404, b'{"error":"NOT_FOUND"}')

class ContainerLabHandler(Handler):
    def trusted_origin(self):
        origin="http://127.0.0.1:18080"
        return self.headers.get("Host")=="127.0.0.1:18080" and self.headers.get("Origin",origin)==origin

    def do_GET(self):
        if not self.trusted_origin():
            self.reply(403,b'{"policy":"DENY"}')
        else:
            super().do_GET()

    def do_POST(self):
        if not self.trusted_origin():
            self.reply(403,b'{"policy":"DENY"}')
        else:
            super().do_POST()

def server(port=0, core_config=None, context_config=None, policy_port=None, mattermost_config=None, enterprise_clock=None, enterprise_collector=None, technical_collector=None, ai_providers=None, *, container_lab=False, collector_guard=None):
    # Explicit, loopback-only LAB activation. No automatic provisioning or
    # trust in request-supplied scope, database paths, or publisher callbacks.
    guarded_config = None
    if collector_guard is not None:
        from collector_admission_fence import scope_key
        from continuous_collector import ROOT, port as lab_port
        if (container_lab or type(collector_guard) is not dict
                or set(collector_guard) != {'scope', 'authority', 'witness', 'restore_permitted'}
                or not all(callable(collector_guard[k]) for k in ('authority', 'witness', 'restore_permitted'))
                or core_config is None or context_config is None):
            raise ValueError('explicit isolated collector configuration required')
        scope = collector_guard['scope']
        scope_key(scope)
        core_port, core_token, _ = core_config
        twin_port, evidence_port, node_id, _ = context_config
        if scope[1] != ROOT or node_id != ROOT:
            raise ValueError('collector root mismatch')
        ports = [lab_port(p) for p in (core_port, twin_port, evidence_port)]
        if len(set(ports)) != len(ports) or (port != 0 and (lab_port(port) in ports)):
            raise ValueError('distinct isolated service ports required')
        if (not isinstance(core_token, str) or not 32 <= len(core_token) <= 256
                or any(not 33 <= ord(c) <= 126 for c in core_token)):
            raise ValueError('invalid Core credential')
        guarded_config = dict(collector_guard,
            graph_reader=lambda: Graph(get(twin_port, '/api/twin/graph')),
            publish_records=lambda rows: create_and_persist(rows, core_port, core_token, evidence_port),
            read_context=lambda run_id: dynamic_context(core_port, core_token, run_id,
                twin_port, evidence_port, node_id, include_signals=True))
    if container_lab:
        if os.environ.get("AIOPS_V3_GAMMA_CONTAINER_LAB")!="1" or os.getuid()==0 or port!=18080 or enterprise_clock is None:
            raise ValueError("explicit nonroot synthetic container profile required")
        http=ThreadingHTTPServer(("0.0.0.0",port),ContainerLabHandler)
    else:
        http = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if guarded_config is not None and (http.server_port in ports or http.server_port in (7770, 7777, 7790)):
        http.server_close()
        raise ValueError('unverified collector listener port')
    http.collector_guard = guarded_config
    http.core_config = core_config
    http.context_config = context_config
    http.policy_port = policy_port
    http.mattermost_config = mattermost_config
    http.approval_gate = DurableApprovalGate(enterprise_clock) if enterprise_clock is not None else ApprovalGate()
    http.enterprise_clock = enterprise_clock
    http.enterprise_collector = enterprise_collector
    http.technical_collector = technical_collector
    http.ai_runtime = None
    if ai_providers is not None:
        try:
            from ai_runtime import AdvisoryRuntime
            if core_config is None or context_config is None:raise ValueError("verified service configuration required")
            forbidden=(http.server_port,core_config[0],context_config[0],context_config[1],policy_port)
            http.ai_runtime=AdvisoryRuntime(enterprise_clock,ai_providers,forbidden)
        except Exception:
            http.server_close()
            raise
    return http

if __name__ == "__main__":
    config = None
    if os.environ.get("V3_LAB_CORE_PORT"):
        config = (int(os.environ["V3_LAB_CORE_PORT"]),
                  os.environ["V3_LAB_CORE_TOKEN"], os.environ["V3_LAB_RUN_ID"])
    with server(core_config=config) as http:
        print("Synthetic demo: http://127.0.0.1:%d" % http.server_port, flush=True)
        http.serve_forever()
