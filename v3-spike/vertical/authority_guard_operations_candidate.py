"""LAB adapter: bind preflight, claim, publication and completion to one identity.

Caller is server-owned; validate measured rows/graph and derive canonical batch
before invoking. Publisher must independently verify persisted Core/Evidence and
return the Run ID and receipt digest, never values from client JSON. All writers
and restore operations must cooperate with the same independent witness.
"""
from dataclasses import dataclass, field
from authority_guard_preflight_candidate import guarded_claim
from authority_restore_guard_candidate import distinct, snapshot, require
from collector_admission_fence import (claim, complete, reconcile, archived_receipt,
                                       scope_key, transaction)


@dataclass(frozen=True)
class AdmissionIdentity:
    scope: tuple
    token: str = field(repr=False)
    generation: int
    episode: str
    batch: str


def publish_once(authority, witness, identity, publish_verified):
    """Publish only after a durable bound claim; failures remain BUSY/PENDING.

    Trusted callback receives the bound scope/generation/episode/batch, never
    credentials or DB connections. A result is a verified Run/digest pair, not
    authority to execute an action. No automatic retry or rearm.
    """
    require(type(identity) is AdmissionIdentity)
    scope, token, generation, episode, batch = (identity.scope, identity.token,
                                               identity.generation, identity.episode,
                                               identity.batch)
    args = (scope, token, generation, episode, batch)
    with guarded_claim(authority, witness, *args):
        claim(authority, *args)
        result = publish_verified(scope, generation, episode, batch)
        require(type(result) is tuple and len(result) == 2)
        run, receipt = result
        complete(authority, *args, run, receipt)
    return {'state': 'COMMITTED', 'run_id': run, 'receipt_sha256': receipt}


def lookup_receipt(authority, witness, identity):
    """Read exact receipt under witness transaction, without setting BUSY.

    This is not permission for publication. Unknown, stale or invalid requests
    cannot poison a READY witness. Cooperating writers are excluded for the
    whole lookup; witness/authority mismatch or BUSY rejects before reading.
    """
    require(type(identity) is AdmissionIdentity)
    distinct(authority, witness)
    with transaction(witness):
        digest = snapshot(authority)
        row = witness.execute('SELECT state,digest,lease FROM guard WHERE id=1').fetchone()
        require(row == ('READY', digest, None))
        scope, token, generation, episode, batch = (identity.scope, identity.token,
                                                   identity.generation, identity.episode,
                                                   identity.batch)
        key = scope_key(scope)
        current = authority.execute('SELECT generation FROM collector_fence WHERE scope=?', (key,)).fetchone()
        require(current is not None and type(generation) is int)
        reader = archived_receipt if generation < current[0] else reconcile
        result = reader(authority, scope, token, generation, episode, batch)
        require(snapshot(authority) == digest)
        return result
