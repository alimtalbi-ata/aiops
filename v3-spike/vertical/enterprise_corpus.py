"""Versioned synthetic enterprise references, scoped before lexical ranking.

Logical validity is not wall-clock validity. Only runs linked by the durable
clock receipt receive historical versions; unbound runs keep legacy references.
"""
import json
import re
from enterprise_context import DOCUMENTS, P, digest

def version_row(doc, tick, version, text=None):
    return {"id":doc["id"],"version":version,"scope":list(doc["scope"]),
            "title":doc["title"],"text":doc["text"] if text is None else text,
            "valid_from_tick":tick,"tenant":"synthetic-demo",
            "provenance":"SYNTHETIC_REFERENCE_ONLY","observed_evidence":False}

def initial_rows(tick):
    return [version_row(d,tick,1) for d in DOCUMENTS]

def change_rows(tick, current):
    if tick%4!=2:
        return []
    doc=next(d for d in DOCUMENTS if d["id"]=="ENT-DOC-001")
    old=next(d for d in current if d["id"]==doc["id"])
    return [version_row(doc,tick,old["version"]+1,
        doc["text"]+f" Synthetic change at logical tick {tick}: verify baseline and affected Payments users before any proposed action.")]

def store(db, rows):
    for row in rows:
        db.execute("INSERT INTO corpus(doc_id,version,valid_from_tick,payload,payload_hash) VALUES(?,?,?,?,?)",
                   (row["id"],row["version"],row["valid_from_tick"],json.dumps(row,sort_keys=True),digest(row)))

def catalog_at(db,tick):
    if type(tick) is not int or tick<1:
        raise ValueError("invalid logical corpus tick")
    stored=db.execute("SELECT doc_id,version,valid_from_tick,payload,payload_hash FROM corpus WHERE valid_from_tick<=? ORDER BY doc_id,version",(tick,)).fetchall()
    latest={}
    baseline={d["id"]:d for d in DOCUMENTS}
    for key,version,valid,raw,h in stored:
        row=json.loads(raw)
        if (digest(row)!=h or row["id"]!=key or row["version"]!=version or row["valid_from_tick"]!=valid
            or key not in baseline or row["scope"]!=baseline[key]["scope"]
            or row["tenant"]!="synthetic-demo" or row["observed_evidence"] is not False
            or row["provenance"]!="SYNTHETIC_REFERENCE_ONLY"):
            raise ValueError("corrupt corpus version")
        previous=latest.get(key)
        if version!=(previous["version"]+1 if previous else 1) or previous and valid<=previous["valid_from_tick"]:
            raise ValueError("invalid corpus history")
        latest[key]=row
    if latest and set(latest)!=set(baseline):
        raise ValueError("incomplete corpus")
    return list(latest.values())

def references(rows, scope, query, *, limit=10):
    if type(limit) is not int or not 1<=limit<=10:
        raise ValueError("invalid limit")
    if not isinstance(query,str) or len(query)>512:
        raise ValueError("invalid query")
    tokens=lambda text:set(re.findall(r"[a-z0-9]{2,40}",text.lower()))
    words=tokens(query)
    ranked=[]
    for row in rows:
        if not set(row["scope"]) & scope:
            continue
        score=len(words & tokens(row["title"]+" "+row["text"]))
        ranked.append((-score,row["id"],row))
    ranked.sort(key=lambda x:(x[0],x[1]))
    return [{**row,"sha256":digest(row),"lexical_score":-score} for score,_,row in ranked[:limit]]
