"""Portal-side read-only ACME laboratory preview. Never exposes evaluator truth."""
from datetime import datetime,timedelta,timezone
import random

MODES=("simple","complex","chaos","smoke_screen")
def preview(mode,seed):
    if mode not in MODES:raise ValueError("invalid mode")
    if not 0 <= seed <= 2**31-1:raise ValueError("invalid seed")
    rng=random.Random(seed)
    base=datetime(2026,10,21,12,0,tzinfo=timezone.utc)
    data=[]
    def add(second,ci,kind,description):
        data.append({"timestamp":(base+timedelta(seconds=second)).isoformat(),
            "scope":"ACME","synthetic":True,"ci_id":ci,"kind":kind,
            "description":description})
    add(0,"ACME-SAN-FABRIC-A","log","FC CRC rising")
    add(30,"ACME-SAN-FABRIC-A","metric","FC CRC delta 38")
    add(35,"ACME-SRV-RHEL01","log","Multipath path degraded")
    add(60,"ACME-SVC-PAYMENTS","metric","Payment p95 340 ms")
    if mode in ("complex","chaos","smoke_screen"):
        add(12,"ACME-STO-PURE01","log","Host-port queue saturation")
        add(42,"ACME-STO-PURE01","metric","Front-end queue depth 110")
        add(72,"ACME-SVC-PAYMENTS","trace","authorize_payment 420 ms")
    if mode in ("chaos","smoke_screen"):
        add(18,"ACME-NET-CORE-A","log","Independent core link flap")
        add(55,"ACME-NET-CORE-A","metric","Packet discards 240")
        add(80,"ACME-SVC-ERP","log","ERP retries elevated")
    if mode=="smoke_screen":
        noise=[("ACME-SAN-FABRIC-B","Routine zoning audit"),
               ("ACME-SVC-ERP","ERP cache occupancy"),
               ("ACME-SRV-RHEL01","Scheduled log rotation"),
               ("ACME-NET-CORE-A","Unrelated interface utilization")]
        for i in range(14):
            ci,desc=noise[i%4]
            add(rng.randrange(100),ci,"log" if i%2==0 else "metric",desc)
    return sorted(data,key=lambda x:x["timestamp"])
