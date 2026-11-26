"""CI-only SQLite backup/restore verification; never overwrite an existing world."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import hashlib

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"vertical"))
from enterprise_clock import EnterpriseClock

def smoke(root):
    root=Path(root)
    if os.environ.get("GITHUB_ACTIONS")!="true" or str(root)!="/tmp/aiops-v3-rootless-ci":
        raise ValueError("disposable CI root required")
    source=EnterpriseClock(root)
    before=source.status()
    activity_before=source.activity()
    corpus_before=source.document_catalog()
    assert before["current_tick"]==8 and not before["pending"]
    backup=root/"backup"/"enterprise-world.sqlite3"
    fd=os.open(backup,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    os.close(fd)
    with closing(source.connect()) as db, closing(sqlite3.connect(backup)) as dest:
        db.backup(dest)
        assert dest.execute("PRAGMA integrity_check").fetchall()==[("ok",)]
        assert not dest.execute("PRAGMA foreign_key_check").fetchall()
    with tempfile.TemporaryDirectory(prefix="world-restore-",dir=root) as tmp:
        restored=EnterpriseClock(tmp)
        with closing(sqlite3.connect(backup)) as db, closing(restored.connect()) as dest:
            db.backup(dest)
        assert restored.status()==before and restored.activity()==activity_before and restored.document_catalog()==corpus_before
        with closing(source.connect()) as a, closing(restored.connect()) as b:
            for table,count in (("journal",8),("measured",2),("technical",2),("activity",8),("corpus",12)):
                order={"corpus":"doc_id,version","knowledge":"doc_id"}.get(table,"tick")
                rows=a.execute("SELECT * FROM "+table+" ORDER BY "+order).fetchall()
                assert len(rows)==count and rows==b.execute("SELECT * FROM "+table+" ORDER BY "+order).fetchall()
        restored.advance(9,lambda _: (_ for _ in ()).throw(AssertionError("nominal tick cannot publish")))
        assert restored.status()["current_tick"]==9 and source.status()==before
        assert len(restored.activity()["records"])==27 and source.activity()==activity_before
        assert restored.document_catalog()["documents"]==corpus_before["documents"] and source.document_catalog()==corpus_before
    print(json.dumps({"classification":"E5_SQLITE_BACKUP_RESTORE","result":"PASS","ticks":8,"technical_captures":2,"measured_captures":2,"restored_next_tick":9,"backup_sha256":hashlib.sha256(backup.read_bytes()).hexdigest(),"production_authorized":False}))

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: poc-clock-backup-smoke.py CI_ROOT")
    smoke(sys.argv[1])
