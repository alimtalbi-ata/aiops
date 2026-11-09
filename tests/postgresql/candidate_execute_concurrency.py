"""CI-only real PostgreSQL locking proof; Worker is a double, not Temporal E2E."""
import os
import pathlib
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

# No configurable destination: only the existing disposable Actions service.
if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('AIOPS_CI_EXECUTE_PG') != 'YES':
    raise SystemExit('Refusing execution outside explicitly enabled GitHub Actions')

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from test_candidate_core_execute import load_execute

DSN = 'host=127.0.0.1 port=5432 dbname=aiops user=aiops connect_timeout=5'
rid = 'CI-EXECUTE-' + uuid.uuid4().hex
entered = threading.Event()
release = threading.Event()
second_connected = threading.Event()
pids = {}
local = threading.local()


def db():
    connection = psycopg.connect(DSN, options='-c statement_timeout=12000 -c lock_timeout=10000')
    pids[local.label] = connection.info.backend_pid
    if local.label == 'second':
        second_connected.set()
    return connection


def dispatch(*args, **kwargs):
    assert kwargs['json']['run_id'] == rid
    assert kwargs['timeout'] == 10
    entered.set()
    if not release.wait(8):
        raise AssertionError('Test coordinator did not release Worker double')
    response = Mock()
    response.json.return_value = {'run_id': rid, 'workflow_id': rid}
    return response


requests = Mock()
requests.post.side_effect = dispatch
execute = load_execute(db, requests)


def call(label):
    local.label = label
    return execute(rid, 'Bearer offline-test')


with psycopg.connect(DSN) as connection:
    connection.execute(
        "insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
        "values(%s,'DEMO','CI-EXECUTE','CREATED',%s)", (rid, rid))

try:
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(call, 'first')
        try:
            assert entered.wait(5), 'First call did not reach Worker'
            second = pool.submit(call, 'second')
            assert second_connected.wait(5), 'Second client did not connect'
            # Observe a real lock dependency, rather than relying on a sleep.
            blocked = False
            deadline = time.monotonic() + 5
            with psycopg.connect(DSN, autocommit=True) as observer:
                while time.monotonic() < deadline:
                    blockers = observer.execute('select pg_blocking_pids(%s)', (pids['second'],)).fetchone()[0]
                    if pids['first'] in blockers:
                        blocked = True
                        break
                    time.sleep(0.02)
            assert blocked, 'Second execute did not wait for first transaction'
            assert requests.post.call_count == 1, 'Duplicate Worker dispatch while lock held'
        finally:
            release.set()
        results = [first.result(timeout=12), second.result(timeout=12)]
    assert requests.post.call_count == 1, 'Retry dispatched Worker again'
    assert results[0]['workflow_id'] == results[1]['workflow_id'] == rid
    assert results[1]['idempotent'] is True
    with psycopg.connect(DSN) as observer:
        assert observer.execute('select workflow_id from aiops.execution_receipts where run_id=%s', (rid,)).fetchall() == [(rid,)]
    print('CANDIDATE_EXECUTE_PG_CONCURRENCY=PASS; worker=double; temporal=NOT_VERIFIED')
finally:
    release.set()
    # Delete only this invocation's synthetic fixture, never truncate tables.
    with psycopg.connect(DSN) as connection:
        connection.execute('delete from aiops.execution_receipts where run_id=%s', (rid,))
        connection.execute('delete from aiops.runs where run_id=%s', (rid,))
