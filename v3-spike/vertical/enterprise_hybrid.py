"""Bounded hybrid lexical BM25 + character TF-IDF cosine retrieval.

No learned embeddings, model inference or authenticated tenant ACL. Scope and
logical validity are checked before constructing the candidate vector space.
"""
from collections import Counter
import math
import re
import unicodedata
from enterprise_context import digest

METHOD="BM25_CHAR_TRIGRAM_TFIDF_RRF_V1"
STOP={"the","a","an","of","to","and","or","for","in","on","is","be","with","at","as","it","by","from","le","la","les","de","des","du","un","une","et","en","pour","sur","dans","au","aux"}

def tokens(text):
    normalized=unicodedata.normalize("NFKD",text.lower())
    plain="".join(c for c in normalized if not unicodedata.combining(c))
    return [w for w in re.findall(r"[a-z0-9]{2,40}",plain) if w not in STOP]

def grams(words):
    return Counter(g for w in words for g in (("^"+w+"$")[i:i+3] for i in range(len(w))))

def cosine(a,b):
    numerator=sum(v*b.get(k,0) for k,v in a.items())
    denominator=math.sqrt(sum(v*v for v in a.values())*sum(v*v for v in b.values()))
    return numerator/denominator if denominator else 0.0

def retrieve(rows,scope,query,tick,limit=5):
    if (not isinstance(query,str) or not 1<=len(query)<=512 or type(tick) is not int or tick<1
        or type(limit) is not int or not 1<=limit<=5 or len(rows)>30):
        raise ValueError("invalid bounded hybrid request")
    eligible=[]
    ids=set()
    for row in rows:
        if row["tenant"]!="synthetic-demo" or not set(row["scope"]) & scope or row["valid_from_tick"]>tick:
            continue
        if row["observed_evidence"] is not False or row.get("production_authorized",False) is not False:
            raise ValueError("unsafe reference")
        raw={k:v for k,v in row.items() if k!="sha256"}
        h=digest(raw)
        if row.get("sha256",h)!=h or row["id"] in ids:
            raise ValueError("invalid document identity")
        ids.add(row["id"])
        eligible.append(({**raw,"sha256":h},tokens(row["title"]+" "+row["text"])))
    query_words=tokens(query)
    result={"classification":"SYNTHETIC_HYBRID_RETRIEVAL_E9","method":METHOD,"logical_tick":tick,
            "candidate_count":len(eligible),"query_sha256":digest(query),"citations":[],
            "learned_embeddings":False,"llm_inference_performed":False,"tenant_acl_qualified":False,
            "production_authorized":False,"operational_decision":"DENY","state":"NO_MATCH"}
    if not eligible or not query_words:
        return result
    words=[Counter(w) for _,w in eligible]
    chars=[grams(w) for _,w in eligible]
    n=len(eligible)
    avg=max(1,sum(sum(w.values()) for w in words)/n)
    word_df=Counter(t for w in words for t in w)
    char_df=Counter(t for g in chars for t in g)
    def weighted(g):
        return {t:(1+math.log(v))*(1+math.log((n+1)/(char_df.get(t,0)+1))) for t,v in g.items()}
    qvec=weighted(grams(query_words))
    scores=[]
    for i,(row,_) in enumerate(eligible):
        counts=words[i]
        norm=1.2*(.25+.75*sum(counts.values())/avg)
        bm25=sum(math.log(1+(n-word_df[t]+.5)/(word_df[t]+.5))*counts[t]*2.2/(counts[t]+norm)
                 for t in set(query_words) if t in counts)
        vector=cosine(qvec,weighted(chars[i]))
        scores.append((row,bm25,vector))
    lexical=sorted((s for s in scores if s[1]>0),key=lambda s:(-s[1],s[0]["id"]))
    # Minimum similarity is a fixed test-fixture heuristic, not calibrated confidence.
    vectors=sorted((s for s in scores if s[2]>=.18),key=lambda s:(-s[2],s[0]["id"]))
    lr={s[0]["id"]:i+1 for i,s in enumerate(lexical)}
    vr={s[0]["id"]:i+1 for i,s in enumerate(vectors)}
    fused=[]
    for row,bm25,vector in scores:
        ident=row["id"]
        if ident not in lr and ident not in vr:
            continue
        score=(1/(60+lr[ident]) if ident in lr else 0)+(1/(60+vr[ident]) if ident in vr else 0)
        fused.append({**row,"bm25_score":round(bm25,6),"vector_cosine":round(vector,6),"rrf_score":round(score,9)})
    result["citations"]=sorted(fused,key=lambda r:(-r["rrf_score"],r["id"]))[:limit]
    if result["citations"]: result["state"]="MATCHED"
    return result
