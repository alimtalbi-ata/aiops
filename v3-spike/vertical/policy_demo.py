"""Decision-only adapter for isolated synthetic lab; never executes an action."""
import http.client
import json

def simulation_decision(port, evidence_count):
    if type(port) is not int or not 1024<=port<=65535 or port in (7770,7777,7790):
        raise ValueError("invalid lab port")
    if type(evidence_count) is not int or not 0<=evidence_count<=20:
        raise ValueError("invalid evidence count")
    payload={"mode":"DEMO","command":"REMEDIATE","severity":"UNKNOWN",
             "confidence":0,"evidence_count":evidence_count,
             "critic_validated":False,"redundancy_ok":False,"human_approved":False}
    conn=http.client.HTTPConnection("127.0.0.1",port,timeout=5)
    try:
        conn.request("POST","/api/policy/check",json.dumps(payload),
                     {"Content-Type":"application/json"})
        response=conn.getresponse()
        raw=response.read(65537)
        if response.status!=200 or len(raw)>65536:
            raise ValueError("Policy unavailable")
        result=json.loads(raw)
        expected=("PASS","SIMULATE") if evidence_count else ("UNKNOWN","HUMAN_APPROVAL")
        if (result.get("state"),result.get("decision"))!=expected:
            raise ValueError("unexpected Policy decision")
        return {"policy_decision":result["decision"],
                "simulation_only":bool(evidence_count),
                "operational_decision":"DENY","executed_on_host":False,
                "production_authorized":False}
    finally:
        conn.close()
