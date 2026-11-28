"""LAB candidate: guard the existing server-owned rearm with a durable witness.

All writers must cooperate with the same witness. This adapter does not install
an HTTP route, generate comparison observations or authenticate the Verify reader.
An uncertain outcome remains BUSY; there is no automatic unlock or retry.
"""
import secrets

from authority_guard_operations_candidate import AdmissionIdentity
from authority_restore_guard_candidate import distinct, snapshot, require
from collector_admission_fence import (
    authenticated, check_episode, identity, rearm, transaction,
    require as fence_require,
)


def rearm_guarded(authority, witness, admission, *, expected_run_id,
                  expected_receipt_sha256, read_verified_recovery):
    """Reuse the existing atomic archive/rearm with a mandatory witness.

    Expected run and receipt and the recovery reader must be resolved by the
    server, never trusted from client JSON. The reader may publish comparison
    evidence only after the durable BUSY lease is acquired.
    """
    require(type(admission) is AdmissionIdentity and callable(read_verified_recovery))
    scope, token, generation, episode, batch = (
        admission.scope, admission.token, admission.generation,
        admission.episode, admission.batch)
    distinct(authority, witness)
    lease = secrets.token_hex(32)
    with transaction(witness):
        before = snapshot(authority)
        require(witness.execute('SELECT state,digest,lease FROM guard WHERE id=1').fetchone()
                == ('READY', before, None))
        check_episode(episode, batch)
        fence_require(identity(expected_run_id, r'RUN-[A-F0-9]{16}')
                      and identity(expected_receipt_sha256, r'[a-f0-9]{64}'))
        _, current = authenticated(authority, scope, token, generation)
        fence_require(current == ('COMMITTED', episode, batch,
                                  expected_run_id, expected_receipt_sha256))
        require(snapshot(authority) == before)
        witness.execute("UPDATE guard SET state='BUSY',lease=? WHERE id=1", (lease,))

    def verified(*args):
        require(args == (scope, generation, episode, batch,
                         expected_run_id, expected_receipt_sha256))
        require(witness.execute('SELECT state,lease FROM guard WHERE id=1').fetchone()
                == ('BUSY', lease))
        proof = read_verified_recovery(*args)
        # Comparison publication must not mutate admission authority.
        require(snapshot(authority) == before)
        require(witness.execute('SELECT state,lease FROM guard WHERE id=1').fetchone()
                == ('BUSY', lease))
        return proof

    # No finally-unlock: a reader failure, NOT_RECOVERED, or lost acknowledgement
    # after the authority commit must retain BUSY across process restarts.
    next_generation = rearm(authority, scope, token, generation, episode, batch,
                            read_verified_recovery=verified)
    require(next_generation == generation + 1)
    _, current = authenticated(authority, scope, token, next_generation)
    require(current == ('ARMED', None, None, None, None))
    after = snapshot(authority)
    with transaction(witness):
        require(witness.execute('SELECT state,lease FROM guard WHERE id=1').fetchone()
                == ('BUSY', lease))
        witness.execute("UPDATE guard SET state='READY',digest=?,lease=NULL WHERE id=1", (after,))
    return {'state': 'ARMED', 'generation': next_generation,
            'production_authorized': False}
