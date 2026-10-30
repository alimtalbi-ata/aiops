MODES={'LIVE','DEMO','REPLAY','STORY'}
STATUSES={'CREATED','RUNNING','WAITING','BLOCKED','RESOLVED','FAILED','CANCELLED'}
ALLOWED={
 'CREATED':{'RUNNING','CANCELLED'},'RUNNING':{'WAITING','BLOCKED','RESOLVED','FAILED','CANCELLED'},
 'WAITING':{'RUNNING','BLOCKED','CANCELLED'},'BLOCKED':{'WAITING','FAILED','CANCELLED'},
 'RESOLVED':set(),'FAILED':set(),'CANCELLED':set()}
STAGES=['INGEST','NORMALIZE','CORRELATE','CMDB','OBSERVE','RAG','DGX_ANALYST','DGX_CRITIC','POLICY','HITL','REMEDIATE','VERIFY','RECONCILE','LEARN']
def initial_stage_state(stage):
    """A run-created receipt completes INGEST; worker stages start pending."""
    return 'PASS' if stage == 'INGEST' else 'PENDING'

def transition(a,b):
    if b not in ALLOWED.get(a,set()): raise ValueError(f'illegal transition {a}->{b}')
def impact_from_paths(direct_impact:float, redundant_paths:int, total_paths:int):
    if total_paths<=0: return ('UNKNOWN',0.0)
    loss=max(0,total_paths-redundant_paths)
    score=min(1.0,max(direct_impact, loss/total_paths))
    if score>=0.75:return ('OUTAGE',score)
    if score>=0.25:return ('DEGRADED',score)
    return ('NONE',score)
