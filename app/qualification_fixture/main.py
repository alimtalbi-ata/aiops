"""Deterministic OpenAI-compatible CI fixture. NEVER a real model or LIVE authority.

Only launched by the isolated local DEMO runner. The fixture validates its
own narrow claim (evidence record present), not incident diagnosis.
"""
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SYNTHETIC CI ONLY - no LLM")
class ChatRequest(BaseModel):
    model: str
    messages: list[dict]
    response_format: dict | None = None

@app.get('/health')
def health():
    return {'status':'ok','provider':'SYNTHETIC_CI_FIXTURE','real_model':False}

@app.post('/v1/chat/completions')
def complete(req: ChatRequest):
    if req.model != 'synthetic-ci-fixture-v1' or len(req.messages) < 2:
        raise HTTPException(422, 'fixture_model_mismatch')
    try:
        payload = json.loads(req.messages[-1]['content'])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, 'fixture_invalid_input') from None
    if payload.get('mode') != 'DEMO' or not payload.get('incident',{}).get('synthetic'):
        raise HTTPException(403, 'fixture_demo_only')
    evidence = payload.get('evidence')
    if not isinstance(evidence,list) or not evidence:
        raise HTTPException(422, 'fixture_requires_evidence')
    ids = [x.get('evidence_id') for x in evidence if isinstance(x,dict)]
    if len(ids) != len(evidence) or any(not isinstance(x,str) or not x for x in ids):
        raise HTTPException(422, 'fixture_requires_evidence_ids')
    eid = ids[0]
    if 'analyst' in payload:
        # Only validates that the supplied evidence record exists, not root cause.
        result = {'contract_version':'2.0','validated':True,'issues':[],
                  'claim_checks':[{'claim':'A synthetic evidence record was supplied',
                                   'supported':True,'supporting_evidence_ids':[eid],
                                   'contradicting_evidence_ids':[]}],
                  'additional_evidence_needed':['Independent live diagnostics for causal attribution'],
                  'unsafe_actions':[],'diagnostic_confidence':0.2,
                  'final_recommendation':'OBSERVE',
                  'limitations':['SYNTHETIC_CI_FIXTURE; no actual model or causal validation']}
    else:
        result = {'contract_version':'2.0','classification':'synthetic_fixture_observation',
                  'severity':'UNKNOWN','severity_rationale':'No independent live severity proof',
                  'hypotheses':[{'id':'SYNTHETIC-H1',
                                 'statement':'A synthetic evidence record exists; cause remains unknown',
                                 'confidence':0.2,'supporting_evidence_ids':[eid],
                                 'contradicting_evidence_ids':[],
                                 'assumptions':['Synthetic CI fixture, not a causal diagnosis']}],
                  'alternatives':[],'recommended_actions':[],
                  'missing_information':['Independent live diagnostic evidence'],
                  'unknowns':['Root cause','Live severity'],'contradictions':[],
                  'confidence':0.2,'confidence_basis':'Synthetic record presence only',
                  'limitations':['SYNTHETIC_CI_FIXTURE; no real model inference']}
    return {'id':'synthetic-ci-only','object':'chat.completion','model':req.model,
            'choices':[{'index':0,'message':{'role':'assistant','content':json.dumps(result)},
                        'finish_reason':'stop'}]}
