"""QA-only reference model: independent SQLite generation fence, not product code."""
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor


@contextmanager
def transaction(path):
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        yield db


class Authority:
    def __init__(self, path):
        self.path = path

    def initialize(self):
        with transaction(self.path) as db:
            db.execute('CREATE TABLE fence (scope TEXT PRIMARY KEY, generation INTEGER NOT NULL, state TEXT NOT NULL)')
            db.execute('CREATE TABLE receipts (scope TEXT, generation INTEGER, episode TEXT, PRIMARY KEY(scope,generation), UNIQUE(scope,episode))')
            db.execute('INSERT INTO fence VALUES (?,0,?)', ('demo/collector/target', 'ARMED'))

    def transition(self, scope, generation, operation, episode=None):
        # Never create a new database when the authority is missing.
        try:
            with closing(sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT generation,state FROM fence WHERE scope=?', (scope,)).fetchone()
                if row is None or row[0] != generation:
                    return 'UNKNOWN_BLOCKED', None
                if operation == 'publish' and row[1] == 'ARMED' and episode:
                    if db.execute('SELECT 1 FROM receipts WHERE scope=? AND episode=?', (scope, episode)).fetchone():
                        return 'UNKNOWN_BLOCKED', None
                    # Atomic reference publication receipt, not external side effect.
                    db.execute('INSERT INTO receipts VALUES (?,?,?)', (scope, generation, episode))
                    state = 'LATCHED'
                elif operation == 'rearm' and row[1] == 'LATCHED':
                    # Test harness only: a real server must verify fresh recovery evidence.
                    state = 'ARMED'
                else:
                    return 'UNKNOWN_BLOCKED', None
                db.execute('UPDATE fence SET generation=?,state=? WHERE scope=?', (generation + 1, state, scope))
                return state, generation + 1
        except sqlite3.Error:
            return 'UNKNOWN_BLOCKED', None

    def count(self):
        with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)) as db:
            return db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    with tempfile.TemporaryDirectory(prefix='v3-authority-') as tmp:
        root = Path(tmp)
        authority = Authority(root / 'authority.sqlite3')
        authority.initialize()
        scope = 'demo/collector/target'
        old = root / 'old-journal.json'
        old.write_text(json.dumps({'scope': scope, 'generation': 0}))
        check('unknown scope denied', authority.transition('other/collector/target', 0, 'publish', 'E0')[0] == 'UNKNOWN_BLOCKED')
        # Concurrent reservations race at the authoritative transaction.
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda e: authority.transition(scope, 0, 'publish', e), ['E1', 'E2']))
        check('one concurrent winner', sorted(s for s, _ in results) == ['LATCHED', 'UNKNOWN_BLOCKED'])
        check('one authoritative receipt', authority.count() == 1)
        authority = Authority(authority.path)  # process-style reopen of independent authority
        restored = json.loads(old.read_text())
        check('restored generation rejected', authority.transition(**restored, operation='publish', episode='E3')[0] == 'UNKNOWN_BLOCKED')
        check('lost ack retry rejected', authority.transition(scope, 0, 'publish', 'E1')[0] == 'UNKNOWN_BLOCKED')
        check('stale rearm denied', authority.transition(scope, 0, 'rearm')[0] == 'UNKNOWN_BLOCKED')
        check('latched publication denied', authority.transition(scope, 1, 'publish', 'E4')[0] == 'UNKNOWN_BLOCKED')
        check('authorized rearm advances generation', authority.transition(scope, 1, 'rearm') == ('ARMED', 2))
        check('legitimate new episode accepted', authority.transition(scope, 2, 'publish', 'E5') == ('LATCHED', 3))
        check('only two receipts', authority.count() == 2)
        unavailable = Authority(root / 'missing.sqlite3')
        check('unavailable authority fail closed', unavailable.transition(scope, 3, 'publish', 'E6')[0] == 'UNKNOWN_BLOCKED')
        check('no accidental authority recreation', not unavailable.path.exists())
    print(json.dumps({'classification': 'V3_QA_AUTHORITY_REFERENCE_MODEL', 'result': 'PASS', 'cases': len(checks), 'checks': checks, 'production_authorized': False, 'limitations': ['Independent SQLite reference model; no actual collector/GAMMA integration', 'Scope authentication and recovery evidence validation not implemented', 'No atomic external publication/outbox proof', 'Simultaneous rollback of authority and journal not protected']}, sort_keys=True))


if __name__ == '__main__':
    main()
