"""Deterministic synthetic activity stream; nominal records never create incidents."""
from enterprise_context import P, ROOT, LYON, digest

APPLICATIONS = (
    (ROOT, "ASSET-PAR", "APP-PAY", (("USER-FIN-01","GROUP-FIN"),("USER-FIN-02","GROUP-FIN"),("USER-DIRECT-01",None))),
    (ROOT, "ASSET-PAR", "APP-CRM", (("USER-SALES-01","GROUP-SALES"),)),
    (LYON, "ASSET-LYO", "APP-HR", (("USER-HR-01","GROUP-HR"),)),
)

def activity_for(step):
    tick=step["tick"]
    phase=step["phase"]
    records=[]
    for index,(root,asset,app,users) in enumerate(APPLICATIONS):
        user,group=users[0 if index==0 and phase=="DEGRADED" else (tick-1)%len(users)]
        # Preserve the actual E2 modeled latency for Payments. CRM alert is
        # a separate modeled observation, not evidence of a shared root cause.
        latency=step["modeled_latency_ms"] if index==0 else 25+((tick*7+index*11)%15)
        if index==1 and phase=="CHANGE":
            latency=85
        severity="INCIDENT_THRESHOLD" if latency>=120 else "ALERT" if latency>=75 else "NOMINAL"
        event="MODEL_RECOVERY" if phase=="MODEL_RECOVERY" and index==0 else "CHANGE" if phase=="CHANGE" else "ACTIVITY"
        scope={"asset_id":P+asset,"application_id":P+app,"user_id":P+user,"occurred_at":step["simulated_at"]}
        if group: scope["group_id"]=P+group
        records.append({"activity_id":f"activity-v1-{tick}-{index}","tick":tick,"resource":root,"scope":scope,
                        "classification":"MODEL_GENERATED","state":severity,
                        "signals":[{"kind":"metric","metric":"latency_ms","unit":"ms","value":latency},
                                   {"kind":"log","message":"Modeled synthetic application request"},
                                   {"kind":"event","event":event}],
                        "incident_eligible":index==0 and severity=="INCIDENT_THRESHOLD" and phase=="DEGRADED",
                        "observed_outage_established":False,"production_authorized":False})
    return records

def decode_activity(step, raw, checksum):
    import json
    records=json.loads(raw)
    if digest(records)!=checksum or records!=activity_for(step):
        raise ValueError("unverified activity journal")
    publication=step["publication"]
    # A threshold is not an incident unless publication is confirmed.
    output=[]
    for row in records:
        linked=publication if row["incident_eligible"] and publication and publication["state"]=="PUBLISHED" else None
        output.append({**row,"run_id":linked["run_id"] if linked else None,
                       "incident_id":linked["incident_id"] if linked else None,
                       "link_semantics":"SAME_MODELED_SCENARIO_NOT_EVIDENCE" if linked else None,
                       "disposition":"INCIDENT_LINKED" if linked else "PENDING_INCIDENT" if row["incident_eligible"] else "ALERT_ONLY" if row["state"]=="ALERT" else "OBSERVATION_ONLY"})
    return output
