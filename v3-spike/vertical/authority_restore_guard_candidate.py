"""LAB candidate, not wired to AIOPS runtime.
Independent witness must never be restored with the collector authority.
All mutating entrypoints and restore orchestration must honor the same guard.
A crash/uncertain result leaves BUSY durably; no automatic unlock.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from collector_admission_fence import transaction


class RestoreBlocked(ValueError):
    pass


def require(ok):
    if not ok:
        raise RestoreBlocked('authority restore guard blocked')


def db_path(db):
    entries = db.execute('PRAGMA database_list').fetchall()
    require(len(entries) == 1 and entries[0][1] == 'main' and bool(entries[0][2]))
    return Path(entries[0][2]).resolve(strict=True)


def distinct(authority, witness):
    require(not db_path(authority).samefile(db_path(witness)))


def open_existing(path):
    return sqlite3.connect(Path(path).resolve(strict=True).as_uri() + '?mode=rw', uri=True)


def snapshot(authority):
    require(not authority.in_transaction)
    authority.execute('BEGIN')
    try:
        schema = authority.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema "
                                   "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        require({r[1] for r in schema if r[0] == 'table'} == {'collector_fence', 'collector_history'})
        rows = [authority.execute('SELECT * FROM collector_fence ORDER BY scope').fetchall(),
                authority.execute('SELECT * FROM collector_history ORDER BY scope,generation').fetchall()]
        require(bool(rows[0]))
        value = hashlib.sha256(json.dumps([schema, rows], sort_keys=True, separators=(',', ':'),
                                         allow_nan=False).encode()).hexdigest()
        authority.commit()
        return value
    except BaseException:
        authority.rollback()
        raise


def provision_witness(authority, witness):
    """Explicit one-time offline bootstrap. Never call on runtime failure."""
    distinct(authority, witness)
    with transaction(witness):
        witness.execute('CREATE TABLE guard (id INTEGER PRIMARY KEY CHECK(id=1), '
                        'state TEXT NOT NULL CHECK(state IN (\'READY\',\'BUSY\')), '
                        'digest TEXT NOT NULL, lease TEXT)')
        witness.execute("INSERT INTO guard VALUES(1,'READY',?,NULL)", (snapshot(authority),))


@contextmanager
def guarded(authority, witness):
    """All callers must use this before any authority operation or publication.
    The witness is committed BUSY before side effects. Any uncertainty blocks.
    """
    distinct(authority, witness)
    lease = secrets.token_hex(32)
    with transaction(witness):
        row = witness.execute('SELECT state,digest,lease FROM guard WHERE id=1').fetchone()
        require(row is not None and row == ('READY', snapshot(authority), None))
        witness.execute("UPDATE guard SET state='BUSY',lease=? WHERE id=1", (lease,))
    # No finally-unlock: a failure, cancellation or crash is uncertain.
    yield
    value = snapshot(authority)
    with transaction(witness):
        row = witness.execute('SELECT state,lease FROM guard WHERE id=1').fetchone()
        require(row == ('BUSY', lease))
        witness.execute("UPDATE guard SET state='READY',digest=?,lease=NULL WHERE id=1", (value,))
