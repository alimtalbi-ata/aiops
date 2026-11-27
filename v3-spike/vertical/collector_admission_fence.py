"""Admission-side synthetic collector fence; database outside collector backup.

Caller owns the private database and authentication transport. A claim is not
permission for host action. Pending claims never retry publication. Rearm requires a server-owned Verify
reader; simultaneous authority rollback still requires an external operator lock.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re


class FenceRejected(ValueError):
    pass


def require(condition):
    if not condition:
        raise FenceRejected('collector authority rejected')


def identity(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def scope_key(scope):
    require(isinstance(scope, tuple) and len(scope) == 3 and scope[0] == 'synthetic-demo'
            and identity(scope[1], r'NODE-CI-[A-Z0-9-]{1,80}')
            and identity(scope[2], r'COLLECTOR-[a-z0-9-]{1,64}'))
    return '/'.join(scope)


def token_hash(token):
    require(identity(token, r'[a-f0-9]{64}'))
    return hashlib.sha256(token.encode()).hexdigest()


@contextmanager
def transaction(db):
    require(not db.in_transaction)
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


# Scope components are validated by scope_key; split only on the final collector
# delimiter, which cannot occur inside a canonical target name.
TARGET_SQL = "substr(scope,1,instr(scope,'/COLLECTOR-')-1)"


def require_single_owner(db, scope):
    target = '/'.join(scope[:2])
    require(db.execute('SELECT COUNT(*) FROM collector_fence WHERE ' + TARGET_SQL + '=?',
                       (target,)).fetchone()[0] == 1)


def historical_run_unused(db, key, run_id):
    return db.execute('SELECT 1 FROM collector_history WHERE scope=? AND (run_id=? OR comparison_run_id=?)',
                      (key, run_id, run_id)).fetchone() is None


def initialize(db):
    """Explicit provisioning only; never call on missing runtime authority."""
    with transaction(db):
        db.execute('CREATE TABLE collector_fence (scope TEXT PRIMARY KEY, credential TEXT NOT NULL, '
                   'generation INTEGER NOT NULL, state TEXT NOT NULL, episode TEXT, batch TEXT, '
                   'run_id TEXT, receipt TEXT)')
        db.execute('CREATE UNIQUE INDEX one_collector_per_target ON collector_fence(' + TARGET_SQL + ')')
        db.execute('CREATE TABLE collector_history (scope TEXT NOT NULL, generation INTEGER NOT NULL, '
                   'episode TEXT NOT NULL, batch TEXT NOT NULL, run_id TEXT NOT NULL, receipt TEXT NOT NULL, '
                   'verify_sha256 TEXT NOT NULL, comparison_run_id TEXT NOT NULL, PRIMARY KEY(scope,generation), '
                   'UNIQUE(scope,episode), UNIQUE(scope,batch), UNIQUE(scope,run_id), UNIQUE(scope,comparison_run_id))')


def provision(db, scope, token):
    with transaction(db):
        scope_key(scope)
        require(db.execute('SELECT 1 FROM collector_fence WHERE ' + TARGET_SQL + '=?',
                           ('/'.join(scope[:2]),)).fetchone() is None)
        db.execute('INSERT INTO collector_fence VALUES (?,?,0,\'ARMED\',NULL,NULL,NULL,NULL)',
                   (scope_key(scope), token_hash(token)))


def authenticated(db, scope, token, generation):
    require(type(generation) is int and generation >= 0)
    key = scope_key(scope)
    require_single_owner(db, scope)
    row = db.execute('SELECT credential,generation,state,episode,batch,run_id,receipt '
                     'FROM collector_fence WHERE scope=?', (key,)).fetchone()
    require(row is not None and hmac.compare_digest(row[0], token_hash(token)) and row[1] == generation)
    return key, row[2:]


def check_episode(episode, batch):
    require(identity(episode, r'[a-f0-9]{32}') and identity(batch, r'[a-f0-9]{64}'))


def claim(db, scope, token, generation, episode, batch):
    """Only a fresh ARMED claim can start publication, after durable commit."""
    check_episode(episode, batch)
    with transaction(db):
        key, row = authenticated(db, scope, token, generation)
        require(row[0] == 'ARMED')
        require(db.execute('SELECT 1 FROM collector_history WHERE scope=? AND (episode=? OR batch=?)',
                           (key, episode, batch)).fetchone() is None)
        db.execute("UPDATE collector_fence SET state='PENDING',episode=?,batch=? WHERE scope=?",
                   (episode, batch, key))
    return 'CLAIMED_NO_EXECUTION'


def complete(db, scope, token, generation, episode, batch, run_id, receipt):
    """Server-only after independently verified publication; no external I/O."""
    check_episode(episode, batch)
    require(identity(run_id, r'RUN-[A-F0-9]{16}') and identity(receipt, r'[a-f0-9]{64}'))
    with transaction(db):
        key, row = authenticated(db, scope, token, generation)
        require(row[1:3] == (episode, batch))
        if row[0] == 'COMMITTED':
            require(row[3:] == (run_id, receipt))
        else:
            require(row[0] == 'PENDING')
            require(historical_run_unused(db, key, run_id))
            db.execute("UPDATE collector_fence SET state='COMMITTED',run_id=?,receipt=? WHERE scope=?",
                       (run_id, receipt, key))


def reconcile(db, scope, token, generation, episode, batch):
    """Read exact receipt reference; a pending outcome stays UNKNOWN_BLOCKED."""
    check_episode(episode, batch)
    with transaction(db):
        _, row = authenticated(db, scope, token, generation)
        require(row[1:3] == (episode, batch) and row[0] in ('PENDING', 'COMMITTED'))
        if row[0] == 'PENDING':
            return {'state': 'UNKNOWN_BLOCKED'}
        return {'state': 'COMMITTED', 'run_id': row[3], 'receipt_sha256': row[4]}


# Proposed bounded LAB freshness window. The trusted reader must return the
# persisted observation time, never substitute a current verification time.
RECOVERY_MAX_AGE_SECONDS = 120


def require_fresh_recovery(proof):
    value = proof.get('recovery_observed_at')
    require(identity(value, r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z'))
    try:
        observed = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise FenceRejected('collector authority rejected') from exc
    age = (datetime.now(timezone.utc) - observed).total_seconds()
    require(0 <= age <= RECOVERY_MAX_AGE_SECONDS)


def rearm(db, scope, token, generation, episode, batch, *, read_verified_recovery):
    """Server-only: caller supplies trusted E17 reader, not client JSON.

    Reader resolves persisted Verify using the exact admission identity and
    returns its stored binding plus the independently observed recovery time.
    This checks returned binding and age, not reader authentication or clock trust.
    No rearm from PENDING. A deployment must independently fence authority
    restores before allowing any claims; this SQLite history cannot do that.
    """
    check_episode(episode, batch)
    with transaction(db):
        _, row = authenticated(db, scope, token, generation)
        require(row[0] == 'COMMITTED' and row[1:3] == (episode, batch))
        run_id, receipt = row[3:]
    proof = read_verified_recovery(scope, generation, episode, batch, run_id, receipt)
    require(isinstance(proof, dict))
    # Freeze the reader result before checking and hashing it.
    proof = json.loads(json.dumps(proof, sort_keys=True, separators=(',', ':'), allow_nan=False))
    binding = proof.get('admission_binding')
    require(isinstance(binding, dict) and type(binding.get('generation')) is int
            and binding == {'scope': list(scope), 'generation': generation, 'episode': episode,
                            'batch': batch, 'run_id': run_id, 'receipt_sha256': receipt})
    require_fresh_recovery(proof)
    require(proof.get('classification') == 'SYNTHETIC_LAB_VERIFY'
            and proof.get('status') == 'RECOVERED' and proof.get('original_run_id') == run_id
            and identity(proof.get('comparison_run_id'), r'RUN-[A-F0-9]{16}')
            and proof['comparison_run_id'] != run_id
            and proof.get('production_authorized') is False
            and proof.get('operational_decision') == 'DENY'
            and proof.get('causality_established') is False)
    proof_hash = hashlib.sha256(json.dumps(proof, sort_keys=True, separators=(',', ':'),
                                          allow_nan=False).encode()).hexdigest()
    with transaction(db):
        key, current = authenticated(db, scope, token, generation)
        require(current == row)
        require_fresh_recovery(proof)
        require(historical_run_unused(db, key, run_id)
                and historical_run_unused(db, key, proof['comparison_run_id']))
        db.execute('INSERT INTO collector_history VALUES (?,?,?,?,?,?,?,?)',
                   (key, generation, episode, batch, run_id, receipt, proof_hash, proof['comparison_run_id']))
        db.execute("UPDATE collector_fence SET generation=generation+1,state='ARMED',episode=NULL,"
                   'batch=NULL,run_id=NULL,receipt=NULL WHERE scope=?', (key,))
    return generation + 1


def archived_receipt(db, scope, token, generation, episode, batch):
    """Authenticated read-only reconciliation of an archived generation."""
    check_episode(episode, batch)
    require(type(generation) is int and generation >= 0)
    with transaction(db):
        key = scope_key(scope)
        require_single_owner(db, scope)
        current = db.execute('SELECT credential,generation FROM collector_fence WHERE scope=?', (key,)).fetchone()
        require(current is not None and hmac.compare_digest(current[0], token_hash(token))
                and generation < current[1])
        row = db.execute('SELECT episode,batch,run_id,receipt,verify_sha256,comparison_run_id '
                         'FROM collector_history WHERE scope=? AND generation=?', (key, generation)).fetchone()
        require(row is not None and row[:2] == (episode, batch))
        return {'state': 'COMMITTED', 'run_id': row[2], 'receipt_sha256': row[3],
                'verify_sha256': row[4], 'comparison_run_id': row[5]}
