"""QA countertest for authority scope and historical run reuse; SQLite only."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from contextlib import closing

spec = importlib.util.spec_from_file_location('fence_under_test', Path(sys.argv[1]))
fence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fence)
SCOPE = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-a')
OTHER = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-b')
TOKEN = 'a' * 64
OTHER_TOKEN = 'b' * 64


def run(n):
    return f'RUN-{n:016X}'


def episode(n):
    return f'{n:032x}'


def batch(n):
    return f'{n:064x}'


def proof(original, comparison):
    return dict(classification='SYNTHETIC_LAB_VERIFY', status='RECOVERED',
                original_run_id=original, comparison_run_id=comparison,
                production_authorized=False, operational_decision='DENY',
                causality_established=False)


def committed(db, generation, n, rid):
    fence.claim(db, SCOPE, TOKEN, generation, episode(n), batch(n))
    fence.complete(db, SCOPE, TOKEN, generation, episode(n), batch(n), rid, batch(n + 100))


def rearm(db, generation, n, original, comparison):
    return fence.rearm(db, SCOPE, TOKEN, generation, episode(n), batch(n),
                       read_verified_recovery=lambda *_: proof(original, comparison))


def attempt(callback):
    try:
        callback()
        return 'ACCEPTED'
    except (fence.FenceRejected, sqlite3.IntegrityError):
        return 'REFUSED'


def main():
    cases = []
    def record(name, actual, expected):
        cases.append(dict(case=name, actual=actual, expected=expected,
                          result='PASS' if actual == expected else 'FAIL'))
    with tempfile.TemporaryDirectory(prefix='v3-fence-scope-') as tmp:
        def database(name):
            db = sqlite3.connect(Path(tmp) / (name + '.sqlite3'))
            fence.initialize(db)
            fence.provision(db, SCOPE, TOKEN)
            return closing(db)
        with database('claim') as db:
            record('first claim', attempt(lambda: fence.claim(db, SCOPE, TOKEN, 0, episode(1), batch(1))), 'ACCEPTED')
            record('second claim same collector', attempt(lambda: fence.claim(db, SCOPE, TOKEN, 0, episode(2), batch(2))), 'REFUSED')
            record('wrong token', attempt(lambda: fence.reconcile(db, SCOPE, OTHER_TOKEN, 0, episode(1), batch(1))), 'REFUSED')
            # Proposed target-level exclusivity, when two credentials are provisioned.
            fence.provision(db, OTHER, OTHER_TOKEN)
            record('same batch second collector same target', attempt(lambda: fence.claim(db, OTHER, OTHER_TOKEN, 0, episode(1), batch(1))), 'REFUSED')
        with database('history') as db:
            committed(db, 0, 1, run(1))
            record('first verified rearm', attempt(lambda: rearm(db, 0, 1, run(1), run(2))), 'ACCEPTED')
            record('old generation claim', attempt(lambda: fence.claim(db, SCOPE, TOKEN, 0, episode(3), batch(3))), 'REFUSED')
            fence.claim(db, SCOPE, TOKEN, 1, episode(3), batch(3))
            record('reuse old incident run', attempt(lambda: fence.complete(db, SCOPE, TOKEN, 1, episode(3), batch(3), run(1), batch(103))), 'REFUSED')
            record('old comparison reused as incident', attempt(lambda: fence.complete(db, SCOPE, TOKEN, 1, episode(3), batch(3), run(2), batch(103))), 'REFUSED')
        with database('comparison') as db:
            committed(db, 0, 1, run(1))
            rearm(db, 0, 1, run(1), run(2))
            committed(db, 1, 3, run(3))
            record('reuse old comparison', attempt(lambda: rearm(db, 1, 3, run(3), run(2))), 'REFUSED')
            record('old incident reused as comparison', attempt(lambda: rearm(db, 1, 3, run(3), run(1))), 'REFUSED')
        with database('new') as db:
            committed(db, 0, 1, run(1))
            rearm(db, 0, 1, run(1), run(2))
            committed(db, 1, 3, run(3))
            record('fresh independent comparison', attempt(lambda: rearm(db, 1, 3, run(3), run(4))), 'ACCEPTED')
    passed = all(c['result'] == 'PASS' for c in cases)
    print(json.dumps(dict(result='PASS' if passed else 'FAIL', cases=cases,
                          production_authorized=False,
                          limitations='Proposed target-level exclusivity and cross-role historical run isolation; direct authority calls, synthetic trusted Verify reader, no service or external action. Contract needs owner confirmation.'), sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
