from fastapi import FastAPI
from pydantic import BaseModel, Field
app=FastAPI(title="AioOps Intelligence",version="2.0.0")
class Analyze(BaseModel):
    incident_id:str
    severity:str="UNKNOWN"
    evidence:list[dict]=[]
    context:dict={}
    mode:str="LIVE"
@app.get("/health")
def health(): return {"status":"ok","component":"intelligence","contract":"analyst-critic-ready"}
@app.post("/api/analyze")
def analyze(x:Analyze):
    evidence_count=len(x.evidence)
    confidence=0.65 if evidence_count else 0.20
    return {"incident_id":x.incident_id,"classification":"UNKNOWN" if not evidence_count else x.severity,
            "severity":{"level":x.severity,"score":confidence,"reason":"evidence-count based baseline; DGX inference may enrich this result"},
            "root_cause":{"hypothesis":"insufficient evidence" if not evidence_count else "requires correlation","confidence":confidence,"evidence":[]},
            "alternative_causes":[],"recommended_actions":[],"decision":{"action":"ENRICH","confidence":confidence,"reason":"evidence-first gate"},
            "missing_information":[] if evidence_count else ["authoritative evidence"],"analyst_version":"r5-baseline"}
