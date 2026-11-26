"""Bounded disposable Linux process, file, SQLite and loopback TCP measurements.

These are lab workload surrogates mapped to fictional Twin nodes, not measurements
of actual enterprise servers, switches, PostgreSQL or storage arrays.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import uuid

P="NODE-CI-ENT-"
PAYLOAD=b"v3-lab-telemetry"*4096
TCP_PAYLOAD=b"v3-lab-echo"*64

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def elapsed(start):
    return max(0.000001,round((time.perf_counter_ns()-start)/1e6,6))

def compute():
    start=time.process_time_ns()
    value=PAYLOAD
    for _ in range(1024):
        value=hashlib.sha256(value).digest()
    cpu=max(0.000001,round((time.process_time_ns()-start)/1e6,6))
    return [("process_cpu_ms","ms","PROCESS_TIME_DELTA",cpu),
            ("process_peak_rss_kib","KiB","LINUX_RUSAGE_MAXRSS",resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)]

def storage(folder):
    file=folder/"storage.bin"
    start=time.perf_counter_ns()
    with file.open("xb") as f:
        count=f.write(PAYLOAD)
        f.flush()
        os.fsync(f.fileno())
    duration=elapsed(start)
    if count!=len(PAYLOAD) or file.read_bytes()!=PAYLOAD:
        raise ValueError("write readback mismatch")
    return [("fsync_write_ms","ms","MONOTONIC_WRITE_FSYNC",duration),
            ("fsync_write_bytes","bytes","EXACT_WRITE_COUNT",count)]

def database(folder):
    with closing(sqlite3.connect(folder/"fixture.sqlite3")) as db, db:
        db.execute("CREATE TABLE synthetic(id INTEGER PRIMARY KEY, amount INTEGER NOT NULL)")
        db.executemany("INSERT INTO synthetic VALUES(?,?)",((i,i*3) for i in range(100)))
        start=time.perf_counter_ns()
        rows=db.execute("SELECT id,amount FROM synthetic WHERE id>=? ORDER BY id",(50,)).fetchall()
        duration=elapsed(start)
        if rows!=[(i,i*3) for i in range(50,100)]:
            raise ValueError("query readback mismatch")
    return [("sqlite_query_ms","ms","MONOTONIC_SQLITE_QUERY",duration),
            ("sqlite_result_rows","rows","SQLITE_FETCH_COUNT",len(rows))]

def receive(sock,count):
    data=bytearray()
    while len(data)<count:
        block=sock.recv(count-len(data))
        if not block: raise ValueError("truncated echo")
        data.extend(block)
    return bytes(data)

def network():
    errors=[]
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
        listener.settimeout(3)
        listener.bind(("127.0.0.1",0))
        port=listener.getsockname()[1]
        if port in (7770,7777,7790): raise ValueError("protected port")
        listener.listen(1)
        def serve():
            try:
                conn,_=listener.accept()
                with conn:
                    conn.settimeout(3)
                    conn.sendall(receive(conn,len(TCP_PAYLOAD)))
            except Exception as exc:
                errors.append(exc)
        thread=threading.Thread(target=serve,daemon=True)
        thread.start()
        try:
            with socket.create_connection(("127.0.0.1",port),timeout=3) as conn:
                start=time.perf_counter_ns()
                conn.sendall(TCP_PAYLOAD)
                result=receive(conn,len(TCP_PAYLOAD))
                duration=elapsed(start)
                if result!=TCP_PAYLOAD: raise ValueError("echo mismatch")
        finally:
            thread.join(4)
        if errors or thread.is_alive(): raise ValueError("echo worker failed")
    return [("loopback_rtt_ms","ms","MONOTONIC_TCP_ECHO",duration),
            ("loopback_echo_bytes","bytes","TCP_ECHO_COUNT",len(result))]

def collect(root):
    root=Path(root)
    if (sys.platform!="linux" or not root.is_absolute() or root==Path("/") or root.resolve()!=root
        or not root.is_dir() or root.stat().st_uid!=os.getuid()):
        raise ValueError("dedicated Linux lab root required")
    # No writes outside the dedicated POC root; each workload has bounded data.
    with tempfile.TemporaryDirectory(prefix="technical-e5-",dir=root) as tmp:
        folder=Path(tmp)
        workloads=[("LINUX-PAR",compute()),("STORAGE-PAR",storage(folder)),
                   ("DB-PAY",database(folder)),("NET-PAR",network())]
    identity=uuid.uuid4().hex
    batches=[]
    for name,metrics in workloads:
        asset=P+name
        base={"source":"technical-isolated-e5","resource":asset,"severity":"warning","tenant":"synthetic-demo","synthetic":True}
        scope={"asset_id":asset,"occurred_at":now()}
        rows=[]
        for metric,unit,method,value in metrics:
            rows.append(dict(base,id=identity+"-"+metric,kind="metric",enterprise=dict(scope,telemetry={
                "classification":"MEASURED_ISOLATED_WORKLOAD","metric":metric,"unit":unit,"method":method,"value":value})))
        rows.append(dict(base,id=identity+"-"+name+"-event",kind="event",enterprise=dict(scope,message="Bounded isolated technical workload completed; no enterprise outage established")))
        batches.append(rows)
    return batches

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: poc-technical-observed.py DEDICATED_ROOT")
    print(json.dumps(collect(sys.argv[1]),allow_nan=False))
