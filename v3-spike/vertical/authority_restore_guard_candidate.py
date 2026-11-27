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


def require_independent_daemons(authority_daemon_id, witness_daemon_id):
    """Fail closed unless IDs come from authenticated, live daemon-info calls.

    This is a contract primitive only: callers must obtain IDs independently
    from each daemon's control socket. It does not create that transport or
    make a same-host witness independent.
    """
    import re
    pattern = r'[a-f0-9]{64}'
    require(isinstance(authority_daemon_id, str) and re.fullmatch(pattern, authority_daemon_id))
    require(isinstance(witness_daemon_id, str) and re.fullmatch(pattern, witness_daemon_id))
    require(authority_daemon_id != witness_daemon_id)
    return True


def _attestation_payload(daemon_id, challenge, role, failure_domain_id):
    require(isinstance(daemon_id, str) and __import__('re').fullmatch(r'[a-f0-9]{64}', daemon_id))
    require(isinstance(challenge, str) and __import__('re').fullmatch(r'[a-f0-9]{64}', challenge))
    require(role in ('authority', 'witness'))
    require(isinstance(failure_domain_id, str) and 1 <= len(failure_domain_id) <= 128)
    return json.dumps({'daemon_id': daemon_id, 'challenge': challenge, 'role': role,
                       'failure_domain_id': failure_domain_id},
                      sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def verify_daemon_attestation(attestation, expected_challenge, expected_role, trust_key):
    """Verify an externally provisioned per-daemon HMAC trust anchor.

    LAB contract only: callers must obtain attestation over an authenticated,
    live control channel and provision trust_key outside that daemon's restore
    domain. This function performs no network I/O or key provisioning.
    """
    import hmac
    require(isinstance(attestation, dict))
    require(isinstance(trust_key, bytes) and len(trust_key) >= 32)
    payload = _attestation_payload(attestation.get('daemon_id'),
                                   attestation.get('challenge'),
                                   attestation.get('role'),
                                   attestation.get('failure_domain_id'))
    require(attestation.get('challenge') == expected_challenge)
    require(attestation.get('role') == expected_role)
    signature = attestation.get('signature')
    require(isinstance(signature, str) and len(signature) == 64)
    expected = hmac.new(trust_key, payload, hashlib.sha256).hexdigest()
    require(hmac.compare_digest(signature, expected))
    return {key: attestation[key] for key in ('daemon_id', 'role', 'failure_domain_id')}


def require_independent_daemon_attestations(authority_attestation, witness_attestation,
                                             challenge, authority_key, witness_key):
    """Require authenticated identities and distinct restore failure domains."""
    import hmac
    require(isinstance(authority_key, bytes) and isinstance(witness_key, bytes))
    require(not hmac.compare_digest(authority_key, witness_key))
    authority = verify_daemon_attestation(authority_attestation, challenge, 'authority', authority_key)
    witness = verify_daemon_attestation(witness_attestation, challenge, 'witness', witness_key)
    require(authority['daemon_id'] != witness['daemon_id'])
    require(authority['failure_domain_id'] != witness['failure_domain_id'])
    return True
