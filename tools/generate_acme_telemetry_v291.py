#!/usr/bin/env python3
"""Generate correlated ACME DEMO telemetry JSONL. No database or API writes."""
import argparse,datetime,json,random

def generate(seed=20261021, count=12):
    rng=random.Random(seed)
    epoch=datetime.datetime(2026,10,21,10,0,tzinfo=datetime.timezone.utc)
    rows=[]
    for idx in range(count):
        t=(epoch+datetime.timedelta(seconds=30*idx)).isoformat()
        degraded=idx>=5
        crc=(rng.randint(0,2) if not degraded else 25+(idx-5)*18)
        latency=round((rng.uniform(5,10) if not degraded else rng.uniform(18,42)),2)
        p95=round((rng.uniform(78,105) if not degraded else rng.uniform(250,390)),2)
        correlation=f"ACME-DEMO-{seed}"
        for kind,ci,measurement,value,unit in [
            ("metric","ACME-SAN-FABRIC-A","fc_crc_errors_delta",crc,"count/30s"),
            ("metric","ACME-STO-PURE01","storage_latency_ms",latency,"ms"),
            ("metric","ACME-SVC-PAYMENTS","payment_p95_ms",p95,"ms"),
        ]:
            rows.append({"timestamp":t,"scope":"ACME","synthetic":True,
                "scenario":"SAN_FABRIC_A_DEGRADATION","correlation_id":correlation,
                "kind":kind,"ci_id":ci,"metric":measurement,"value":value,"unit":unit,
                "source":"acme-simulator-v291"})
        if idx==5:
            rows.append({"timestamp":t,"scope":"ACME","synthetic":True,
                "scenario":"SAN_FABRIC_A_DEGRADATION","correlation_id":correlation,
                "kind":"log","ci_id":"ACME-SAN-FABRIC-A","severity":"WARNING",
                "message":"Port FC 1/12 CRC increments above baseline; investigate optics and link counters",
                "source":"acme-simulator-v291"})
    return rows

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--seed",type=int,default=20261021)
    parser.add_argument("--intervals",type=int,default=12)
    options=parser.parse_args()
    if not 1<=options.intervals<=10000:parser.error("intervals must be 1..10000")
    for event in generate(options.seed,options.intervals):
        print(json.dumps(event,ensure_ascii=False))
