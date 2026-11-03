"""Source-only negative contract tests for ACME Core same-Run journey."""
import hashlib
import importlib.util
import json
import re
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
core_pkg = types.ModuleType('core')
core_pkg.__path__ = []
core = types.ModuleType('core.acme_sandbox')
core.TENANT, core.SCENARIO, core.ISSUER = 'ACME-TEST', 'ACME-SAN-PAYMENTS', 'TWIN_ACME_SIMULATED'
core.HEADERS = {'Cache-Control': 'no-store'}
core.ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{2,99}\Z')
core.ident = lambda prefix, value, length=24: prefix + hashlib.sha256(
    (core.TENANT + ':' + value).encode()).hexdigest()[:length].upper()
core.read = lambda conn, attempt: None
core.require_enabled = lambda: None
core.auth = lambda value: None if value == 'Bearer internal-only' else (
    (_ for _ in ()).throw(HTTPException(401, 'unauthorized')))
core_pkg.acme_sandbox = core
shared = types.ModuleType('shared')
shared.__path__ = []
shared_db = types.ModuleType('shared.db')
shared_db.db = lambda: None
_keys = ('core', 'core.acme_sandbox', 'shared', 'shared.db')
_previous = {key: sys.modules.get(key) for key in _keys}
sys.modules.update({'core': core_pkg, 'core.acme_sandbox': core,
                    'shared': shared, 'shared.db': shared_db})
spec = importlib.util.spec_from_file_location(
    'core.acme_sandbox_journey', ROOT / 'app/core/acme_sandbox_journey.py')
journey = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = journey
spec.loader.exec_module(journey)
for _key, _value in _previous.items():
    if _value is None:
        sys.modules.pop(_key, None)
    else:
        sys.modules[_key] = _value

ATTEMPT = 'ACME-TEST-T2-REPLAY'
RUN = core.ident('RUN-SIM-', ATTEMPT)
INC = core.ident('INC-SIM-', ATTEMPT)
TICKET = core.ident('SIM-GLPI-', ATTEMPT)
PROP = core.ident('PROP-SIM-', ATTEMPT)
SOURCE_IDS = [core.ident('SYN-EVT-', ATTEMPT + ':' + str(i), 20) for i in range(1, 8)]
TIME = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def fixture(resolved=False):
    snapshot = dict(schema='aiops.core-acme-sandbox-readback.v1', tenant_id=core.TENANT,
                    scenario_id=core.SCENARIO, attempt_id=ATTEMPT, mode='SIMULATION',
                    source='SYNTHETIC_SIMULATOR', source_hashes_qualified=True,
                    ticket_authority='SIMULATED_ONLY', approval_issuer=core.ISSUER,
                    human_approved=False, live_effects_allowed=False,
                    real_glpi_writes_allowed=False, execution_allowed=False,
                    effect_allowed=False, run_status='RESOLVED' if resolved else 'PREPARED',
                    incident_status='RESOLVED' if resolved else 'PREPARED',
                    source_event_count=7, source_event_ids=SOURCE_IDS,
                    incident_id=INC, run_id=RUN, ticket_id=TICKET, proposal_id=PROP,
                    request_sha256='a'*64, worker_receipt_verified=resolved,
                    terminal_ticket_receipt_verified=resolved,
                    approval_id=core.ident('SIM-APP-', ATTEMPT) if resolved else None,
                    worker_receipt_sha256='b'*64 if resolved else None,
                    terminal_ticket_sha256='c'*64 if resolved else None)
    rows = []
    for i, eid in enumerate(SOURCE_IDS, 1):
        payload = {'tenant_id': core.TENANT, 'run_id': RUN, 'incident_id': INC,
                   'source_event_id': eid, 'sequence': i, 'synthetic': True}
        rows.append((i, 'SOURCE', 'OBSERVED', 'PASS', TIME, eid,
                     [core.ident('EVID-SIM-', ATTEMPT + ':' + str(1+(i%2)))], payload))
    rows.append((8, 'RUN', 'SIMULATED_PREPARED', 'PREPARED', TIME,
                 core.ident('SIM-PREPARED-', ATTEMPT), [],
                 {'tenant_id': core.TENANT, 'synthetic': True,
                  'ticket_id': TICKET, 'proposal_id': PROP,
                  'execution_allowed': False, 'effect_allowed': False}))
    if resolved:
        rows.append((9, 'RUN', 'SIMULATED_RESOLVED', 'RESOLVED', TIME+timedelta(seconds=5),
                     core.ident('SIM-RESOLVED-', ATTEMPT), [],
                     {'tenant_id': core.TENANT, 'approval_id': snapshot['approval_id'],
                      'worker_receipt_verified': True,
                      'worker_receipt_sha256': snapshot['worker_receipt_sha256'],
                      'terminal_ticket_sha256': snapshot['terminal_ticket_sha256'],
                      'execution_allowed': False, 'effect_allowed': False}))
    return snapshot, rows


@pytest.mark.parametrize('resolved', [False, True])
def test_same_run_projection_is_synthetic(resolved):
    snapshot, rows = fixture(resolved)
    value = journey.project_journey(snapshot, rows, ATTEMPT)
    assert (value['incident_id'], value['run_id'], value['ticket_id']) == (INC, RUN, TICKET)
    assert len(value['timeline']) == (9 if resolved else 8)
    assert [r['source_event_id'] for r in value['timeline'][:7]] == SOURCE_IDS
    assert value['twin_graph_019'] == 'NOT_BOUND_TO_THIS_RUN'
    assert value['analyst'] == 'SYNTHETIC_FIXTURE_NOT_INDEPENDENTLY_ATTESTED'
    assert value['human_approved'] is False and value['effect_allowed'] is False
    assert all(len(r['record_sha256']) == 64 for r in value['timeline'])


@pytest.mark.parametrize('mutation', [
    'foreign_run', 'foreign_tenant', 'reordered', 'extra', 'missing', 'float_count',
    'wrong_ticket', 'live_flag', 'bad_source', 'boolean_sequence', 'backward_clock',
    'forged_terminal', 'premature_terminal', 'missing_worker_receipt',
])
def test_fail_closed_on_mixed_replay(mutation):
    snapshot, rows = fixture(mutation in ('forged_terminal', 'missing_worker_receipt'))
    if mutation == 'foreign_run': rows[0][7]['run_id'] = 'RUN-FOREIGN'
    elif mutation == 'foreign_tenant': rows[0][7]['tenant_id'] = 'FOREIGN'
    elif mutation == 'reordered': rows[0], rows[1] = rows[1], rows[0]
    elif mutation == 'extra': rows.append(rows[-1])
    elif mutation == 'missing': rows.pop()
    elif mutation == 'float_count': snapshot['source_event_count'] = 7.0
    elif mutation == 'wrong_ticket': rows[7][7]['ticket_id'] = 'SIM-GLPI-FOREIGN'
    elif mutation == 'live_flag': snapshot['live_effects_allowed'] = True
    elif mutation == 'bad_source': rows[0] = (*rows[0][:5], 'SYN-EVT-FOREIGN', *rows[0][6:])
    elif mutation == 'boolean_sequence': rows[0] = (True, *rows[0][1:])
    elif mutation == 'backward_clock':
        rows[7] = (*rows[7][:4], TIME-timedelta(seconds=1), *rows[7][5:])
    elif mutation == 'forged_terminal': rows[8][7]['effect_allowed'] = True
    elif mutation == 'premature_terminal':
        snapshot['run_status'] = snapshot['incident_status'] = 'RESOLVED'
    elif mutation == 'missing_worker_receipt': snapshot['worker_receipt_verified'] = False
    with pytest.raises(HTTPException) as exc:
        journey.project_journey(snapshot, rows, ATTEMPT)
    assert exc.value.status_code == 503


def test_auth_before_db(monkeypatch):
    monkeypatch.setattr(journey, 'db', lambda: (_ for _ in ()).throw(AssertionError('db used')))
    with pytest.raises(HTTPException) as exc:
        journey.journey(ATTEMPT, authorization='Bearer wrong')
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        journey.journey('../foreign', authorization='Bearer internal-only')
    assert exc.value.status_code == 422


def test_one_read_only_snapshot(monkeypatch):
    snapshot, rows = fixture()
    class Cursor:
        def fetchall(self): return rows
    class Conn:
        def __init__(self): self.sql = []
        def execute(self, sql, args=None):
            self.sql.append((sql, args))
            return Cursor() if args else None
        def __enter__(self): return self
        def __exit__(self, *args): return False
    conn = Conn()
    monkeypatch.setattr(journey, 'db', lambda: conn)
    monkeypatch.setattr(core, 'read', lambda c, attempt: snapshot)
    response = journey.journey(ATTEMPT, authorization='Bearer internal-only')
    assert response.status_code == 200
    assert len(json.loads(response.body)['timeline']) == 8
    assert conn.sql[0][0] == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    assert conn.sql[1][1] == (RUN,)
    assert conn.sql[1][0].lower().startswith('select ')


def test_endpoint_get_only():
    assert {tuple(sorted(route.methods)) for route in journey.router.routes} == {('GET',)}
