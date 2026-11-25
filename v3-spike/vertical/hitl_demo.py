"""In-memory demo approval gate; never authorizes host execution."""
import hashlib
import json
import secrets
import time

class ApprovalGate:
    def __init__(self):
        self.pending={}
    @staticmethod
    def binding(incident,run,evidence):
        if not incident or not run or not evidence:
            raise ValueError("Missing context")
        return hashlib.sha256(json.dumps([incident,run,evidence],sort_keys=True,separators=(",",":")).encode()).hexdigest()
    def request(self,incident,run,evidence):
        if len(self.pending)>=100:
            raise ValueError("Demo queue full")
        key=secrets.token_urlsafe(24)
        self.pending[key]=(self.binding(incident,run,evidence),time.monotonic()+300)
        return {"request_id":key,"decision":"HUMAN_APPROVAL","operational_decision":"DENY"}
    def decide(self,key,incident,run,evidence,approved):
        entry=self.pending.pop(key,None)
        valid=entry is not None and entry[1]>=time.monotonic() and secrets.compare_digest(entry[0],self.binding(incident,run,evidence))
        return {"decision":"SIMULATE_ONLY" if valid and approved is True else "DENY",
                "classification":"SYNTHETIC_HITL_DEMO","operational_decision":"DENY",
                "executed_on_host":False,"production_authorized":False}
