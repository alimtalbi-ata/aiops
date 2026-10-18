from fastapi import FastAPI
from pydantic import BaseModel
app=FastAPI(title="AioOps RAG",version="2.0.0")
class Query(BaseModel): query:str; incident_id:str|None=None; top_k:int=10
@app.get("/health")
def health(): return {"status":"ok","component":"rag","mode":"evidence-first"}
@app.post("/api/query")
def query(x:Query):
    return {"query":x.query,"incident_id":x.incident_id,"items":[],"top_k":min(max(x.top_k,1),50),
            "source_policy":"authoritative-and-provenance-required","status":"EMPTY"}
