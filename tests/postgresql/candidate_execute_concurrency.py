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

# Exercise the actual checkpoint route against PostgreSQL, not a SQL simulator.
import ast
from test_candidate_core_execute import HTTPException

source = pathlib.Path(__file__).resolve().parents[2] / 'app/core/main.py'
function = next(n for n in ast.parse(source.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'checkpoint')
function.decorator_list = []

def checkpoint_db():
    return psycopg.connect(DSN, options='-c statement_timeout=12000 -c lock_timeout=10000')

namespace = {'db': checkpoint_db, 'auth': lambda _: None, 'bearer': lambda x: x,
             'Header': lambda default=None: default, 'HTTPException': HTTPException}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
checkpoint = namespace['checkpoint']
checkpoint_rid = 'CI-CHECKPOINT-' + uuid.uuid4().hex

def save_checkpoint(version, stage='POLICY', workflow=None):
    return checkpoint(checkpoint_rid, {'stage': stage, 'version': version,
                                      'workflow_id': workflow})

def refused(version, stage='POLICY', workflow=None, status=409):
    try:
        save_checkpoint(version, stage, workflow)
    except HTTPException as error:
        assert error.status_code == status
    else:
        raise AssertionError('Conflicting checkpoint accepted')

with checkpoint_db() as connection:
    connection.execute("insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                       "values(%s,'DEMO','CI-CHECKPOINT','CREATED',%s)",
                       (checkpoint_rid, checkpoint_rid))
try:
    save_checkpoint(1, 'INGEST')
    save_checkpoint(1, 'INGEST', checkpoint_rid)  # canonical identity enrichment
    refused(0, 'INGEST')
    refused(1, 'POLICY')
    refused(2, workflow='FOREIGN')
    refused(True, status=422)
    barrier = threading.Barrier(2)
    def race(version):
        barrier.wait(timeout=5)
        try:
            save_checkpoint(version)
            return 200
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        low, high = pool.submit(race, 2), pool.submit(race, 3)
        assert low.result(timeout=15) in (200, 409)
        assert high.result(timeout=15) == 200
    save_checkpoint(3)  # exact retry and absent identity preserve canonical owner
    with checkpoint_db() as connection:
        assert connection.execute('select stage,version,workflow_id from aiops.run_checkpoints where run_id=%s',
                                  (checkpoint_rid,)).fetchone() == ('POLICY', 3, checkpoint_rid)
        connection.execute('update aiops.run_checkpoints set workflow_id=%s where run_id=%s',
                           ('FOREIGN', checkpoint_rid))
    refused(4, workflow=checkpoint_rid)  # never adopt a foreign stored owner
    with checkpoint_db() as connection:
        assert connection.execute('select version,workflow_id from aiops.run_checkpoints where run_id=%s',
                                  (checkpoint_rid,)).fetchone() == (3, 'FOREIGN')
    print('CANDIDATE_CHECKPOINT_PG_MONOTONIC=PASS; concurrent_clients=2; temporal=NOT_VERIFIED')
finally:
    with checkpoint_db() as connection:
        connection.execute('delete from aiops.run_checkpoints where run_id=%s', (checkpoint_rid,))
        connection.execute('delete from aiops.runs where run_id=%s', (checkpoint_rid,))
