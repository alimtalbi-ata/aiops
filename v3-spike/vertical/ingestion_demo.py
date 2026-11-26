"""Bounded synthetic ingestion, no external collector or production data."""
import math
from correlation_demo import correlate

def ingest(records):
    if not isinstance(records,list) or not 1<=len(records)<=100:
        raise ValueError("Invalid batch size")
    events=[]
    for row in records:
        if not isinstance(row,dict) or row.get("synthetic") is not True or row.get("tenant")!="synthetic-demo":
            raise ValueError("Synthetic tenant required")
        kind=row.get("kind")
        if kind not in ("metric","log","event"):
            raise ValueError("Unknown signal kind")
        event={"id":row["id"],"source":kind+":"+row["source"],
               "resource":row["resource"],"severity":row["severity"],"tenant":row["tenant"]}
        if "observation" in row:
            obs=row["observation"]
            if (kind!="metric" or not isinstance(obs,dict) or set(obs)!={"metric","phase","value"}
                or obs["metric"]!="latency_ms" or obs["phase"] not in ("baseline","incident","recovery")
                or type(obs["value"]) not in (int,float) or not 0<obs["value"]<=1e9
                or not math.isfinite(obs["value"])):
                raise ValueError("Invalid synthetic latency observation")
            event["observation"]=dict(obs)
        if "enterprise" in row:
            from enterprise_context import normalize
            event["enterprise"]=normalize(row["enterprise"],kind)
            if "scenario" in event["enterprise"] and "observation" in event:
                raise ValueError("scenario metrics cannot masquerade as latency observations")
            if "telemetry" in event["enterprise"] and "observation" in event:
                raise ValueError("technical telemetry cannot masquerade as latency observation")
            if "measurement" in event["enterprise"]:
                from statistics import median
                if "observation" not in event or event["observation"]["value"]!=round(median(event["enterprise"]["measurement"]["samples_ms"]),3):
                    raise ValueError("measured median does not match samples")
        if event.get("observation",{}).get("phase")=="recovery" and "measurement" not in event.get("enterprise",{}):
            raise ValueError("recovery requires measured lab samples")
        events.append(event)
    result=correlate(events)
    result["ingestion"]={"received":len(records),"unique":sum(i["alert_count"] for i in result["incidents"]),
                         "classification":"SYNTHETIC_NORMALIZED_SIGNALS"}
    return result
