"""Private same-target collector restart journal; not rollback-resistant storage."""
from contextlib import closing
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
from statistics import median
from continuous_collector import Collector,require

STATES={"COMMISSIONING","ARMED","LATCHED","UNKNOWN_BLOCKED"}

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)
def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()
def private_file(path):
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and not info.st_mode&0o077 and info.st_nlink==1,
            "private journal file required")

class DurableCollector(Collector):
    def __init__(self,target_port,gamma_port,root,*,initialize=False):
        super().__init__(target_port,gamma_port)
        root=Path(root)
        require(root.is_absolute() and root!=Path("/") and root.resolve()==root
                and root.is_dir() and root.stat().st_uid==os.getuid() and not root.stat().st_mode&0o077,
                "private collector root required")
        self.path=root/"collector.sqlite3"
        self.fd=os.open(root/"collector.lock",os.O_CREAT|os.O_NOFOLLOW|os.O_RDWR,0o600)
        try:
            private_file(root/"collector.lock")
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if initialize:
                fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
                os.close(fd)
                with closing(self.connect()) as db,db:
                    db.execute("CREATE TABLE state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL, sha256 TEXT NOT NULL)")
                self.checkpoint(initial=True)
            else:
                private_file(self.path)
                with closing(self.connect()) as db:
                    row=db.execute("SELECT payload,sha256 FROM state WHERE singleton=1").fetchone()
                require(row is not None,"missing collector state")
                payload=json.loads(row[0])
                require(digest(payload)==row[1],"collector journal hash mismatch")
                self.restore(payload)
                self.checkpoint()
        except BaseException:
            self.close()
            raise

    def connect(self):
        private_file(self.path)
        db=sqlite3.connect("file:"+str(self.path)+"?mode=rw",uri=True,timeout=5)
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def snapshot(self):
        return {"version":1,"target_port":self.target_port,"gamma_port":self.gamma_port,
                "state":self.state,"baseline":self.baseline,"run_id":self.run_id}

    def restore(self,payload):
        require(isinstance(payload,dict) and set(payload)==set(DurableCollector.snapshot(self))
                and payload["version"]==1 and payload["target_port"]==self.target_port
                and payload["gamma_port"]==self.gamma_port and payload["state"] in STATES,
                "journal scope mismatch")
        b=payload["baseline"]
        if b is not None:
            require(isinstance(b,dict) and set(b)=={"at","samples","median"} and isinstance(b["samples"],list)
                    and len(b["samples"])==5 and all(type(v) in (int,float) and math.isfinite(v) and 0<v<=2000 for v in b["samples"])
                    and b["median"]==round(median(b["samples"]),3) and b["median"]<=40,
                    "invalid saved baseline")
            datetime.strptime(b["at"],"%Y-%m-%dT%H:%M:%SZ")
        state,rid=payload["state"],payload["run_id"]
        require(state=="COMMISSIONING" or b is not None,"missing baseline")
        require((state=="LATCHED" and isinstance(rid,str) and re.fullmatch(r"RUN-[A-F0-9]{16}",rid))
                or (state!="LATCHED" and rid is None),"invalid saved run")
        self.state,self.baseline,self.run_id=state,b,rid
        # A crash breaks consecutiveness; never count a pre-crash window.
        self.nominal=self.degraded=0

    def checkpoint(self,initial=False):
        payload=self.snapshot()
        with closing(self.connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            if initial:
                db.execute("INSERT INTO state VALUES(1,?,?)",(canonical(payload),digest(payload)))
            else:
                count=db.execute("UPDATE state SET payload=?,sha256=? WHERE singleton=1",(canonical(payload),digest(payload))).rowcount
                require(count==1,"missing durable state")

    def observe(self):
        if self.state=="ARMED" and self.baseline is not None:
            age=(datetime.now(timezone.utc)-datetime.strptime(self.baseline["at"],"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds()
            if not 0<=age<=110:
                # Require new commissioning; never publish against stale history.
                self.state="COMMISSIONING"
                self.baseline=None
                self.nominal=self.degraded=0
                self.checkpoint()
        return super().observe()

    def close(self):
        if getattr(self,"fd",None) is not None:
            os.close(self.fd)
            self.fd=None

    def __enter__(self): return self
    def __exit__(self,*args): self.close()
