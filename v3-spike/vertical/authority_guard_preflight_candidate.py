"""LAB only: stage a claim preflight under the witness lock before marking BUSY.
All writers must cooperate; no runtime installation or rearm/restore wiring.
"""
from contextlib import contextmanager
import secrets
from authority_restore_guard_candidate import distinct, snapshot, require
from collector_admission_fence import (transaction, authenticated, check_episode,
                                       require as fence_require)


@contextmanager
def guarded_claim(authority, witness, scope, token, generation, episode, batch):
    """Authorize only a fresh claim, preserving READY for known pre-claim refusals.
    Caller must execute claim and all publication/reconciliation in this lease.
    No exception after BUSY may automatically unlock.
    """
    distinct(authority, witness)
    lease = secrets.token_hex(32)
    with transaction(witness):
        digest = snapshot(authority)
        row = witness.execute('SELECT state,digest,lease FROM guard WHERE id=1').fetchone()
        require(row == ('READY', digest, None))
        # Read-only validation with no publication or authority mutation.
        check_episode(episode, batch)
        key, current = authenticated(authority, scope, token, generation)
        fence_require(current[0] == 'ARMED')
        fence_require(authority.execute('SELECT 1 FROM collector_history WHERE scope=? AND (episode=? OR batch=?)',
                                       (key, episode, batch)).fetchone() is None)
        require(snapshot(authority) == digest)
        witness.execute("UPDATE guard SET state='BUSY',lease=? WHERE id=1", (lease,))
    yield
    value = snapshot(authority)
    with transaction(witness):
        require(witness.execute('SELECT state,lease FROM guard WHERE id=1').fetchone() == ('BUSY', lease))
        witness.execute("UPDATE guard SET state='READY',digest=?,lease=NULL WHERE id=1", (value,))
