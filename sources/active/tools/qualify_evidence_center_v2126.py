#!/usr/bin/env python3
"""Local offline ACME qualification. No network or container operations."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
try:
    from tools.summarize_core_historical_v2125 import summarize
except ModuleNotFoundError:
    from summarize_core_historical_v2125 import summarize
EXPECTED=('index.html','ACME-MISSION-CONTROL.html','ACME-HISTORICAL-AUDIT.html')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def qualify(run_path,ledger_path,evidence_path,repo,output):
    sources={'run':run_path,'ledger':ledger_path,'evidence':evidence_path}
    if any(not p.is_file() or p.is_symlink() for p in sources.values()):
        raise ValueError('input must be a regular non-symlink JSON file')
    if output.exists() and (output.is_symlink() or not output.is_dir() or any(output.iterdir())):
        raise ValueError('output must be absent or empty directory')
    report=summarize(*(json.loads(sources[k].read_text(encoding='utf-8')) for k in sources))
    if any(report[k]['missing_from_export'] for k in ('analyst_evidence','critic_evidence','event_evidence')):
        raise ValueError('evidence references missing; fail closed')
    if report['run_mode']!='DEMO' or report['run_status']!='BLOCKED':
        raise ValueError('unexpected historical state')
    generator=repo/'tools/export_acme_evidence_center_v2124.py'
    if not generator.is_file():raise ValueError('missing generator')
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(output,0o700)
    summary_file=output/'historical-summary.json'
    summary_file.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.chmod(summary_file,0o600)
    kit=output/'kit'
    subprocess.run([sys.executable,str(generator),'--input',str(summary_file),'--output',str(kit)],
       check=True,capture_output=True,text=True,timeout=60)
    manifest=json.loads((kit/'manifest.json').read_text(encoding='utf-8'))
    listed={x['name']:x['sha256'] for x in manifest.get('files',[])}
    if set(listed)!=set(EXPECTED) or any(digest(kit/name)!=listed[name] for name in EXPECTED):
        raise ValueError('manifest checksum mismatch')
    if manifest.get('dgx_independently_attested') is not False or manifest.get('live_execution_qualified') is not False:
        raise ValueError('unsupported attestation')
    qualification={'version':'2.12.6','run_id':report['run_id'],
      'collected_by':'OPERATOR_AUTHENTICATED_CORE_EXPORTS',
      'authentication_independently_attested':False,
      'source_files_sha256':{k:digest(v) for k,v in sources.items()},
      'summary_sha256':digest(summary_file),'kit_files_sha256':listed,
      'reference_check':'PASS','recorded_critic_validation':report['critic_validation_declarations'],
      'recorded_policy_states':report['policy_decision_states'],
      'dgx_independently_attested':False,'live_execution_qualified':False,'raw_payloads_in_bundle':False}
    final=output/'qualification.json'
    final.write_text(json.dumps(qualification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.chmod(final,0o600)
    return qualification
def main():
    parser=argparse.ArgumentParser()
    for k in ('run','ledger','evidence','repo','output'):
        parser.add_argument('--'+k,required=True,type=Path)
    a=parser.parse_args()
    result=qualify(a.run,a.ledger,a.evidence,a.repo,a.output)
    print('AIOPS_V2126_QUALIFICATION=PASS')
    print('RUN='+result['run_id'])
    print('OUTPUT='+str(a.output))
if __name__=='__main__':main()
