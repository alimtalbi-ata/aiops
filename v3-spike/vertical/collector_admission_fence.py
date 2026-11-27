"""Admission-side synthetic collector fence; database outside collector backup.

Caller owns the private database and authentication transport. A claim is not
permission for host action. Pending claims never retry publication. No rearm
or automatic recovery from simultaneous authority rollback is implemented.
"""
from contextlib import contextmanager
import hashlib
import hmac
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


def initialize(db):
    """Explicit provisioning only; never call on missing runtime authority."""
    with transaction(db):
        db.execute('CREATE TABLE collector_fence (scope TEXT PRIMARY KEY, credential TEXT NOT NULL, '
                   'generation INTEGER NOT NULL, state TEXT NOT NULL, episode TEXT, batch TEXT, '
                   'run_id TEXT, receipt TEXT)')


def provision(db, scope, token):
    with transaction(db):
        db.execute('INSERT INTO collector_fence VALUES (?,?,0,\'ARMED\',NULL,NULL,NULL,NULL)',
                   (scope_key(scope), token_hash(token)))


def authenticated(db, scope, token, generation):
    require(type(generation) is int and generation >= 0)
    key = scope_key(scope)
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
