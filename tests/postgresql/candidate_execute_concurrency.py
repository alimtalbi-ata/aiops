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

# Two different Run rows must still serialize the global command receipt key.
import json
from types import SimpleNamespace
command_fn = next(n for n in ast.parse(source.read_text()).body
                  if isinstance(n, ast.FunctionDef) and n.name == 'command')
command_fn.decorator_list = []
command_key = 'CI-COMMAND-' + uuid.uuid4().hex
command_runs = [command_key + '-A', command_key + '-B']
command_barrier = threading.Barrier(2)
command_entered = threading.Event()

def command_event(connection, run_id, *args, **kwargs):
    # Hold the winning transaction until the other client attempts the same key.
    command_entered.set()
    time.sleep(0.15)

command_scope = dict(namespace, Command=SimpleNamespace, json=json,
                     new=lambda _: 'CI-RCPT-' + uuid.uuid4().hex,
                     transition=lambda old, new: None, append_event=command_event)
exec(compile(ast.Module(body=[command_fn], type_ignores=[]), str(source), 'exec'), command_scope)

def command_race(run_id):
    command_barrier.wait(timeout=5)
    request = SimpleNamespace(command='START', expected_version=1, idempotency_key=command_key)
    try:
        return 200, command_scope['command'](run_id, request)
    except HTTPException as error:
        return error.status_code, None

with checkpoint_db() as connection:
    for run_id in command_runs:
        connection.execute("insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                           "values(%s,'DEMO','CI-COMMAND','CREATED',%s)", (run_id, run_id))
try:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(command_race, run_id) for run_id in command_runs]
        outcomes = [future.result(timeout=15) for future in futures]
    assert sorted(status for status, _ in outcomes) == [200, 409], outcomes
    winner = next(response['run_id'] for status, response in outcomes if status == 200)
    loser = next(run_id for run_id in command_runs if run_id != winner)
    with checkpoint_db() as connection:
        assert connection.execute('select run_id,command from aiops.command_receipts where idempotency_key=%s',
                                  (command_key,)).fetchall() == [(winner, 'START')]
        assert connection.execute('select status,version from aiops.runs where run_id=%s',
                                  (loser,)).fetchone() == ('CREATED', 1)
    request = SimpleNamespace(command='START', expected_version=1, idempotency_key=command_key)
    assert command_scope['command'](winner, request)['run_id'] == winner
    print('CANDIDATE_COMMAND_PG_CONCURRENCY=PASS; clients=2; loser_unchanged=true; temporal=NOT_VERIFIED')
finally:
    with checkpoint_db() as connection:
        connection.execute('delete from aiops.command_receipts where idempotency_key=%s', (command_key,))
        for run_id in command_runs:
            connection.execute('delete from aiops.runs where run_id=%s', (run_id,))


# Gate evidence provenance is checked with the actual PostgreSQL JSON operators.
gate_fn = next(n for n in ast.parse(source.read_text()).body
               if isinstance(n, ast.FunctionDef) and n.name == 'gate')
gate_fn.decorator_list = []
gate_scope = dict(namespace, json=json, new=lambda _: 'CI-GATE-' + uuid.uuid4().hex)
exec(compile(ast.Module(body=[gate_fn], type_ignores=[]), str(source), 'exec'), gate_scope)
gate_rid = 'CI-GATE-' + uuid.uuid4().hex
gate_eid = gate_rid + '-EVIDENCE'
with checkpoint_db() as connection:
    connection.execute("insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                       "values(%s,'DEMO','CI-GATE','CREATED',%s)", (gate_rid, gate_rid))
try:
    for provenance, allowed in (({'run_id': 'FOREIGN'}, False), ({'run_id': None}, False),
                                ({'run_id': ''}, False), ({'run_id': 42}, False),
                                ({'run_id': gate_rid}, True), ({}, True)):
        with checkpoint_db() as connection:
            connection.execute('delete from aiops.gates where run_id=%s', (gate_rid,))
            gate_eid = gate_rid + '-EVIDENCE-' + uuid.uuid4().hex
            # Append-only evidence stays intact in the disposable CI database.
            connection.execute("insert into aiops.evidence(evidence_id,source,claim,confidence,payload_hash,provenance) "
                               "values(%s,'ci-gate','fixture',0.9,%s,%s)",
                               (gate_eid, gate_eid, json.dumps(provenance)))
        try:
            gate_scope['gate'](gate_rid, dict(stage='OBSERVE', state='PASS',
                evidence_ids=[gate_eid], required_evidence=['observation']), 'Bearer offline-test')
            assert allowed, 'foreign evidence admitted'
        except HTTPException as error:
            assert not allowed and error.status_code == 422
        with checkpoint_db() as connection:
            assert connection.execute('select count(*) from aiops.gates where run_id=%s',
                                      (gate_rid,)).fetchone()[0] == int(allowed)
    print('CANDIDATE_GATE_PG_RUN_BINDING=PASS; legacy_owner_absent=compatible; category_proof=NOT_VERIFIED')
finally:
    with checkpoint_db() as connection:
        connection.execute('delete from aiops.gates where run_id=%s', (gate_rid,))
        connection.execute('delete from aiops.runs where run_id=%s', (gate_rid,))
