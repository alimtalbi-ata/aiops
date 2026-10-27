#!/usr/bin/env python3
"""Assemble local offline hybrid demo from Core exports and optional legacy evidence pages."""
import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]

def assemble(run, ledger, evidence, legacy_kit=None):
    replay = HERE / 'AIOPS-REAL-STACK-REPLAY.html'
    if replay.exists() or replay.is_symlink():
        raise ValueError('Refusing to overwrite existing replay; use a clean extracted kit')
    spec = importlib.util.spec_from_file_location('real_replay', HERE/'tools/build_real_replay.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    paths={'run':Path(run),'ledger':Path(ledger),'evidence':Path(evidence)}
    model=m.build_model(*(m.load(paths[k]) for k in ('run','ledger','evidence')))
    temp=HERE/'replay-generated'
    if temp.exists():raise ValueError('Refusing existing replay-generated directory')
    m.write(model,temp,paths)
    shutil.copy2(temp/'AIOPS-REAL-STACK-REPLAY.html',replay)
    if legacy_kit:
        src=Path(legacy_kit)
        if not src.is_dir() or src.is_symlink():raise ValueError('invalid evidence kit')
        dst=HERE/'evidence'
        if dst.exists():raise ValueError('evidence destination already exists')
        dst.mkdir()
        for name in ('index.html','ACME-MISSION-CONTROL.html','ACME-HISTORICAL-AUDIT.html','manifest.json'):
            p=src/name
            if p.is_symlink() or not p.is_file():raise ValueError('missing or symlinked evidence: '+name)
            shutil.copy2(p,dst/name)
    digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    listed=['AIOPS-HYBRID-COMMAND.html','AIOPS-STAR-DEMO.html','AIOPS-REAL-STACK-REPLAY.html','GUIDE.html']
    output={'version':'2.13.4','run_id':model['run_id'],'provenance':{'star':'SIMULATED_TARGET','replay':'OPERATOR_SUPPLIED_EXPORT','evidence':'UNATTESTED_OFFLINE'},'dgx_independently_attested':False,'live_execution_qualified':False,'executor_fencing_qualified':False,'files':{p:digest(HERE/p) for p in listed},'replay_summary_sha256':digest(temp/'replay-summary.json')}
    (HERE/'hybrid-manifest.json').write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return output

if __name__=='__main__':
    a=argparse.ArgumentParser()
    for name in ('run','ledger','evidence'):a.add_argument('--'+name,required=True,type=Path)
    a.add_argument('--legacy-kit',type=Path)
    x=a.parse_args()
    print(json.dumps(assemble(x.run,x.ledger,x.evidence,x.legacy_kit),indent=2,ensure_ascii=False))
    print('AIOPS_HYBRID_V2134=PASS')
