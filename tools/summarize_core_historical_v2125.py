#!/usr/bin/env python3
"""Offline summary of operator-provided historical JSON; never output freeform payloads."""
import argparse
import json
from collections import Counter
from pathlib import Path
EXPECTED_RUN = 'RUN-A4449145A6E377FF'
def summarize(run, ledger, evidence):
    meta = run.get('run')
    if not isinstance(meta,dict) or any(x.get('run_id') != EXPECTED_RUN for x in (meta,ledger,evidence)):
        raise ValueError('run identity mismatch')
    def rows(obj,key):
        value=obj.get(key)
        if not isinstance(value,list) or not all(isinstance(x,dict) for x in value):
            raise ValueError('invalid collection: '+key)
        return value
    events=rows(run,'events');stages=rows(run,'stages');items=rows(evidence,'items')
    analyses=rows(ledger,'analyses');critiques=rows(ledger,'critiques');policy=rows(ledger,'policy_decisions')
    evidence_ids=[x.get('evidence_id') for x in items]
    if any(not isinstance(x,str) or not x for x in evidence_ids) or len(set(evidence_ids))!=len(evidence_ids):
        raise ValueError('invalid evidence identifiers')
    known=set(evidence_ids)
    def check(records):
        refs=set()
        for record in records:
            ids=record.get('evidence_ids',[])
            if not isinstance(ids,list) or any(not isinstance(x,str) or not x for x in ids):
                raise ValueError('invalid reference')
            refs.update(ids)
        return {'references':len(refs),'found_in_export':len(refs & known),'missing_from_export':len(refs-known)}
    return {'run_id':EXPECTED_RUN,'run_status':meta.get('status'),'run_mode':meta.get('mode'),
        'events':len(events),'stages':len(stages),'evidence_records':len(items),
        'analyst_records':len(analyses),'critic_records':len(critiques),'policy_decisions':len(policy),
        'analyst_evidence':check(analyses),'critic_evidence':check(critiques),'event_evidence':check(events),
        'critic_validation_declarations':dict(Counter('TRUE' if c.get('validated') is True else 'FALSE' if c.get('validated') is False else 'UNKNOWN' for c in critiques)),
        'policy_decision_states':dict(Counter(str(p.get('state','UNKNOWN')) for p in policy)),
        'dgx_independently_attested':False,'live_execution_qualified':False}
def main():
    ap=argparse.ArgumentParser()
    for k in ('run','ledger','evidence','output'):ap.add_argument('--'+k,type=Path,required=True)
    args=ap.parse_args()
    result=summarize(*(json.loads(getattr(args,k).read_text(encoding='utf-8')) for k in ('run','ledger','evidence')))
    if args.output.is_symlink():raise ValueError('symlink output refused')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    args.output.chmod(0o600)
    print('AIOPS_V2125_SUMMARY=PASS')
if __name__=='__main__':main()
