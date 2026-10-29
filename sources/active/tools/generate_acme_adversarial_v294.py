#!/usr/bin/env python3
"""ACME adversarial incident scenarios. Local JSON only; never launches real incidents."""
import argparse,json,random
from datetime import datetime,timedelta,timezone

ASSETS={"fabric_a":"ACME-SAN-FABRIC-A","fabric_b":"ACME-SAN-FABRIC-B",
        "storage":"ACME-STO-PURE01","server":"ACME-SRV-RHEL01",
        "payments":"ACME-SVC-PAYMENTS","erp":"ACME-SVC-ERP",
        "network":"ACME-NET-CORE-A"}
MODES=("simple","complex","chaos","smoke_screen")

def generate(mode="chaos",seed=20261021):
    if mode not in MODES: raise ValueError("unsupported mode")
    rng=random.Random(seed)
    base=datetime(2026,10,21,12,0,tzinfo=timezone.utc)
    cid="ACME-EXERCISE-"+mode.upper()+"-"+str(seed)
    visible=[];truth=[]
    def add(offset,asset,kind,message,metric=None,value=None,noise=False,root=None):
        record={"timestamp":(base+timedelta(seconds=offset)).isoformat(),
          "scope":"ACME","synthetic":True,"exercise_id":cid,"kind":kind,
          "ci_id":ASSETS[asset],"message":message,"source":"acme-chaos-v294"}
        if metric is not None:record.update(metric=metric,value=value)
        visible.append(record)
        if root:truth.append({"root_cause_id":root,"asset_id":ASSETS[asset],
                              "onset":record["timestamp"]})
    add(0,"fabric_a","log","Fibre Channel port 1/12 CRC increasing",
        root="RC-FC-OPTIC")
    add(30,"fabric_a","metric","CRC errors delta",metric="fc_crc_delta",value=38)
    add(35,"server","log","dm-multipath degraded path; alternate paths operational")
    add(60,"payments","metric","Payment response p95 ms",metric="payment_p95_ms",value=340)
    if mode in ("complex","chaos","smoke_screen"):
        add(12,"storage","log","Storage host port queue saturation",
            root="RC-STORAGE-QUEUE")
        add(42,"storage","metric","Front-end queue depth",metric="front_end_queue_depth",value=110)
        add(72,"payments","trace","authorize_payment latency spike",
            metric="duration_ms",value=420)
    if mode in ("chaos","smoke_screen"):
        add(18,"network","log","Independent core link flap detected",
            root="RC-NETWORK-LINK")
        add(55,"network","metric","Core packet discard spike",
            metric="packet_discards_delta",value=240)
        add(80,"erp","log","ERP retry volume elevated in separate service")
    if mode=="smoke_screen":
        noise=[
          ("fabric_b","log","Routine fabric B zoning audit completed"),
          ("erp","metric","ERP cache occupancy high but stable"),
          ("server","log","Scheduled log rotation complete"),
          ("network","metric","Unrelated interface utilization spike"),
        ]
        for j in range(14):
            asset,kind,msg=noise[j%len(noise)]
            add(rng.randrange(0,100),asset,kind,msg,
                metric=("background_metric" if kind=="metric" else None),
                value=(rng.randint(1,90) if kind=="metric" else None),noise=True)
    visible.sort(key=lambda x:x["timestamp"])
    truth_unique={r["root_cause_id"]:r for r in truth}
    return {"observations":visible,
      "ground_truth":{"scope":"ACME","exercise_id":cid,"scenario":mode,
        "root_causes":list(truth_unique.values()),
        "unrelated_observation_count":14 if mode=="smoke_screen" else 0,
        "evaluation_only":True,"not_for_analyst_prompt":True}}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=MODES,default="chaos")
    ap.add_argument("--seed",type=int,default=20261021)
    ap.add_argument("--observations",required=True)
    ap.add_argument("--truth",required=True)
    args=ap.parse_args()
    from pathlib import Path
    p=Path(args.observations);t=Path(args.truth)
    if p.resolve()==t.resolve():ap.error("truth and observations must have separate paths")
    result=generate(args.mode,args.seed)
    p.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in result["observations"]))
    t.write_text(json.dumps(result["ground_truth"],ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"mode":args.mode,"observations":len(result["observations"]),
      "root_causes_hidden":len(result["ground_truth"]["root_causes"]),
      "scope":"ACME","written":["observations","truth"]}))
if __name__=="__main__":main()
