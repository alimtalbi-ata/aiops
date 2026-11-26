"""Local synthetic runbooks: lexical retrieval, not observed evidence or vendor authority."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

CATALOG=Path(__file__).with_name("synthetic_runbooks.json")

def _unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:
            raise ValueError("duplicate catalog field")
        result[k]=v
    return result

def load_catalog():
    fd=os.open(CATALOG,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=32768:
            raise ValueError("invalid corpus")
        with os.fdopen(fd,"rb",closefd=False) as f:
            raw=f.read(32769)
        after=os.fstat(fd)
        if len(raw)!=before.st_size or (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise ValueError("corpus changed while reading")
    finally:
        os.close(fd)
    data=json.loads(raw,object_pairs_hook=_unique)
    if set(data)!={"classification","version","documents"} or data["classification"]!="SYNTHETIC_REFERENCE_ONLY" or type(data["version"]) is not int or data["version"]!=1:
        raise ValueError("invalid corpus classification")
    rows=data["documents"]
    if not isinstance(rows,list) or not 1<=len(rows)<=100:
        raise ValueError("invalid corpus size")
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={"doc_id","asset","topics","title","text"}:
            raise ValueError("invalid document")
        if not re.fullmatch(r"SYN-[A-Z0-9-]{1,80}",row["doc_id"]) or row["doc_id"] in seen or not re.fullmatch(r"NODE-CI-[A-Z0-9-]{1,80}",row["asset"]):
            raise ValueError("invalid document scope")
        seen.add(row["doc_id"])
        if not isinstance(row["topics"],list) or not 1<=len(row["topics"])<=20 or any(not isinstance(t,str) or not re.fullmatch(r"[a-z]{2,32}",t) for t in row["topics"]):
            raise ValueError("invalid topics")
        if any(not isinstance(row[k],str) or not 1<=len(row[k])<=1024 for k in ("title","text")):
            raise ValueError("invalid document text")
    return rows,hashlib.sha256(raw).hexdigest()

def references(context, retrieval, *, limit=3):
    if (context.get("classification")!="SYNTHETIC_LAB_CONTEXT"
        or context.get("production_authorized") is not False
        or context.get("policy")!="DENY" or retrieval.get("run_id")!=context.get("run_id")
        or retrieval.get("production_authorized") is not False
        or type(limit) is not int or not 1<=limit<=5):
        raise ValueError("unverified document scope")
    root=context.get("root")
    rows,digest=load_catalog()
    # Retrieval query is derived from verified observations, not unrestricted user text.
    query={"latency","baseline","regression","response"} if (retrieval["topic"]=="rca" and retrieval["matches"] and context.get("diagnosis",{}).get("hypothesis")=="LATENCY_REGRESSION_OBSERVED") else set()
    ranked=[]
    for row in rows:
        if row["asset"]!=root: continue
        score=len(query.intersection(row["topics"]))
        if score: ranked.append((-score,row["doc_id"],row))
    ranked.sort(key=lambda x:(x[0],x[1]))
    citations=[{"doc_id":row["doc_id"],"title":row["title"],"text":row["text"],"asset":row["asset"],
                "doc_sha256":hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
                "lexical_score":-score,"provenance":"SYNTHETIC_REFERENCE_ONLY","observed_evidence":False}
               for score,_,row in ranked[:limit]]
    return {"classification":"SYNTHETIC_DOCUMENT_RETRIEVAL","run_id":context["run_id"],
            "state":"MATCHED" if citations else "UNKNOWN","catalog_sha256":digest,
            "citations":citations,"truncated":len(ranked)>limit,"llm_inference_performed":False,
            "causality_established":False,"operational_decision":"DENY","production_authorized":False}
