"""Opt-in E27 synthetic advisory runtime. No automatic inference or operational actions."""
import json,os,stat,threading
from urllib.parse import urlsplit
from dual_model_advisory import config
from ai_invocation_ledger import InvocationLedger

def provider_pair(value,forbidden_ports=()):
    if not isinstance(value,dict) or set(value)!={"analyst","critic"}:raise ValueError("explicit two providers required")
    a,c=config(value["analyst"]),config(value["critic"])
    ports=[urlsplit(p["endpoint"]).port for p in (a,c)]
    if len(set(ports))!=2 or a["model"]==c["model"] or set(ports)&set(forbidden_ports):
        raise ValueError("distinct isolated providers required")
    return a,c

def read_config(root):
    # Explicit file only, not environment-discovered or caller-supplied endpoints.
    path=root/"ai-runtime.json"
    try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except FileNotFoundError:return None
    with os.fdopen(fd,"rb") as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1:
            raise ValueError("unsafe AI runtime config")
        raw=f.read(4097)
    if len(raw)>4096:raise ValueError("oversized AI runtime config")
    from dual_model_advisory import strict_json
    data=strict_json(raw)
    provider_pair(data)
    return data

class AdvisoryRuntime:
    def __init__(self,clock,providers,forbidden_ports=()):
        if clock is None:raise ValueError("dedicated clock required")
        self.providers=provider_pair(providers,forbidden_ports)
        self.ledger=InvocationLedger(clock.path.parent.parent)
        if self.ledger.clock.path!=clock.path:raise ValueError("ledger clock mismatch")
        self.lock=threading.Lock()
    def execute(self,history_loader):
        if not self.lock.acquire(blocking=False):raise ValueError("advisory runtime busy")
        try:
            history=history_loader()
            result=self.ledger.execute_rag(history,*self.providers,timeout_seconds=120)
            persisted=self.ledger.read(result["review_id"])
            if persisted["receipt_sha256"]!=result["receipt_sha256"] or persisted["record"]["invocations"]!=result["assessment"]["invocations"]:
                raise ValueError("unverified persisted review")
            return {"classification":"SYNTHETIC_GAMMA_AI_RUNTIME_E27","review_id":result["review_id"],
                "receipt_sha256":result["receipt_sha256"],"run_ids":persisted["record"]["run_ids"],
                "assessment":result["assessment"],"operational_decision":"DENY","production_authorized":False,
                "tenant_acl_qualified":False}
        finally:self.lock.release()
