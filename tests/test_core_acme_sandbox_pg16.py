"""Disposable PG16 Core ACME sandbox, zero GLPI/LIVE/host effects."""
import concurrent.futures
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from core import acme_sandbox as core

ROOT = Path(__file__).resolve().parents[1]
TOKEN = 'ci-core-acme-sandbox-internal-only-not-human'
CHAIN = ['001_schema.sql', '004_operational_model.sql',
         '009_ai_decision_ledger.sql', '010_evidence_identity.sql',
         '011_hitl_decision_outbox.sql', '012_itsm_xref_read.sql',
         '013_actor_delegation_replay_ledger.sql',
         '014_hitl_reject_terminal_receipts.sql',
         '015_core_run_event_idempotency.sql', '016_acme_sandbox_attempts.sql',
         '017_acme_sandbox_prepared_transition.sql',
         '018_acme_sandbox_ticket_terminal_receipts.sql']

def intent(attempt):
    return {'attempt_id': attempt, 'tenant_id': 'ACME-TEST',
            'scenario_id': 'ACME-SAN-PAYMENTS', 'mode': 'SIMULATION',
            'approval_issuer': 'TWIN_ACME_SIMULATED',
            'idempotency_key': attempt, 'live_effects_allowed': False}

class SandboxPG16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = os.environ['DATABASE_URL']
        parsed = urlsplit(cls.original)
        cls.name = 'aiops_core_acme_sandbox_ci'
        cls.url = urlunsplit((parsed.scheme, parsed.netloc, '/' + cls.name, '', ''))
        cls.prev = {k: os.environ.get(k) for k in
                    ('AIOPS_INTERNAL_TOKEN', 'AIOPS_ACME_SANDBOX_ENABLED')}
        os.environ.update({'AIOPS_INTERNAL_TOKEN': TOKEN,
                           'AIOPS_ACME_SANDBOX_ENABLED': 'true'})
        with psycopg.connect(cls.original, autocommit=True) as admin:
            admin.execute(sql.SQL('create database {}').format(sql.Identifier(cls.name)))
        os.environ['DATABASE_URL'] = cls.url
        try:
            with psycopg.connect(cls.url) as db:
                for migration in CHAIN:
                    db.execute((ROOT / 'db/migrations' / migration).read_text())
            app = FastAPI()
            app.include_router(core.router)
            cls.client = TestClient(app)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        os.environ['DATABASE_URL'] = cls.original
        for key, value in cls.prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        with psycopg.connect(cls.original, autocommit=True) as admin:
            admin.execute('select pg_terminate_backend(pid) from pg_stat_activity '
                          'where datname=%s and pid<>pg_backend_pid()', (cls.name,))
            admin.execute(sql.SQL('drop database if exists {}').format(
                sql.Identifier(cls.name)))

    def post(self, attempt, payload=None, token=TOKEN):
        return self.client.post('/api/sandbox/acme/e2e',
                                json=payload if payload is not None else intent(attempt),
                                headers={'Authorization': 'Bearer ' + token})

    def get(self, attempt, token=TOKEN):
        return self.client.get('/api/sandbox/acme/e2e/' + attempt,
                               headers={'Authorization': 'Bearer ' + token})

    def test_01_opt_in_and_capability(self):
        value = self.client.get('/api/sandbox/acme/capabilities').json()
        self.assertEqual((value['component'], value['tenant_id']), ('core', 'ACME-TEST'))
        self.assertTrue(value['isolated'])
        self.assertFalse(value['human_approval_claimed'])
        os.environ['AIOPS_ACME_SANDBOX_ENABLED'] = 'false'
        try:
            self.assertEqual(self.client.get('/api/sandbox/acme/capabilities').status_code, 503)
            self.assertEqual(self.post('ACME-SIM-DISABLED').status_code, 503)
        finally:
            os.environ['AIOPS_ACME_SANDBOX_ENABLED'] = 'true'

    def test_02_one_run_seven_sources_evidence_and_prepared(self):
        attempt = 'ACME-SIM-COREPOSITIVE'
        response = self.post(attempt)
        self.assertEqual(response.status_code, 200, response.text)
        r = response.json()
        self.assertEqual((r['incident_status'], r['run_status'], r['ticket_status']),
                         ('PREPARED', 'PREPARED', 'PREPARED'))
        self.assertEqual(r['ticket_authority'], 'SIMULATED_ONLY')
        self.assertEqual((r['source_event_count'], r['evidence_count']), (7, 2))
        self.assertEqual(len(set(r['source_event_ids'])), 7)
        self.assertTrue(r['source_hashes_qualified'])
        self.assertEqual(r['source'], 'SYNTHETIC_SIMULATOR')
        self.assertEqual(r['analysis_kind'], 'SYNTHETIC_FIXTURE')
        self.assertTrue(r['analysis_validated'] and r['critic_validated'])
        self.assertIsNone(r['approval_id'])
        self.assertFalse(r['execution_allowed'] or r['effect_allowed'])
        self.assertEqual(self.get(attempt).json()['run_id'], r['run_id'])
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute("select count(*) from aiops.run_events "
                                        "where run_id=%s and stage='SOURCE'",
                                        (r['run_id'],)).fetchone()[0], 7)
            for table in ('effect_receipts', 'approval_records',
                          'itsm_xref_events', 'hitl_reject_terminal_receipts'):
                self.assertEqual(db.execute('select count(*) from aiops.' + table).fetchone()[0], 0)

    def test_03_idempotent_replay_restart_and_concurrency(self):
        attempt = 'ACME-SIM-RESTART'
        a = self.post(attempt).json()
        b = self.post(attempt).json()
        self.assertFalse(a['idempotent'])
        self.assertTrue(b['idempotent'])
        app = FastAPI()
        app.include_router(core.router)
        with TestClient(app) as restarted:
            c = restarted.get('/api/sandbox/acme/e2e/' + attempt,
                              headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(c.status_code, 200)
        self.assertEqual(c.json()['source_event_ids'], a['source_event_ids'])
        parallel = 'ACME-SIM-CONCURRENT'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda _: self.post(parallel), range(2)))
        self.assertEqual([r.status_code for r in replies], [200, 200])
        self.assertEqual(sorted(r.json()['idempotent'] for r in replies), [False, True])
        self.assertEqual(len({r.json()['run_id'] for r in replies}), 1)

    def test_04_negative_tenant_live_issuer_replay_extra(self):
        for key, value in [('tenant_id', 'FOREIGN'), ('mode', 'LIVE'),
                           ('approval_issuer', 'HUMAN_IDP'),
                           ('live_effects_allowed', True),
                           ('idempotency_key', 'DIFFERENT')]:
            attempt = 'ACME-SIM-NEG-' + key.upper()
            payload = intent(attempt)
            payload[key] = value
            self.assertEqual(self.post(attempt, payload).status_code, 403)
        attempt = 'ACME-SIM-EXTRA'
        payload = intent(attempt)
        payload['foreign_claim'] = 'human'
        self.assertEqual(self.post(attempt, payload).status_code, 422)
        self.assertEqual(self.get('FOREIGN-ATTEMPT').status_code, 404)

    def test_05_bearer_not_human_or_tenant_grant(self):
        self.assertEqual(self.post('ACME-SIM-BADTOKEN', token='wrong').status_code, 401)
        # HTTP clients reject non-ASCII header bytes before transport; test the
        # Core auth fence directly rather than misclassifying a client exception.
        with self.assertRaises(HTTPException) as bad:
            core.auth('Bearer nonascii-é')
        self.assertEqual(bad.exception.status_code, 401)
        self.assertEqual(self.get('ACME-SIM-COREPOSITIVE', token='wrong').status_code, 401)
        self.assertEqual(self.client.get('/api/sandbox/acme/e2e/ACME-SIM-COREPOSITIVE').status_code, 401)
        self.assertFalse(self.client.get('/api/sandbox/acme/capabilities').json()['real_glpi_writes_allowed'])

    def test_06_tamper_and_immutable_audit(self):
        attempt = 'ACME-SIM-TAMPER'
        run = self.post(attempt).json()['run_id']
        with psycopg.connect(self.url) as db:
            db.execute("update aiops.run_events set payload=payload||%s::jsonb "
                       "where run_id=%s and stage='SOURCE' and sequence=1",
                       (json.dumps({'tenant_id': 'FOREIGN'}), run))
        self.assertEqual(self.get(attempt).status_code, 503)
        stale = 'ACME-SIM-STALE'
        stale_run = self.post(stale).json()['run_id']
        with psycopg.connect(self.url) as db:
            db.execute("update aiops.evidence set observed_at=now()-interval '10 minutes' "
                       "where provenance->>'run_id'=%s", (stale_run,))
        self.assertEqual(self.get(stale).status_code, 503)
        with psycopg.connect(self.url) as db:
            with self.assertRaises(psycopg.Error):
                with db.transaction():
                    db.execute('delete from aiops.acme_sandbox_attempts '
                               'where attempt_id=%s', (attempt,))
            self.assertEqual(db.execute('select count(*) from aiops.actor_delegation_nonce_ledger').fetchone()[0], 0)

    def test_07_migration_reapply_rollback_and_pg16_restore(self):
        migration = (ROOT / 'db/migrations/016_acme_sandbox_attempts.sql').read_text()
        with psycopg.connect(self.url) as db:
            db.execute('savepoint replay')
            db.execute(migration)
            db.execute('rollback to savepoint replay')
            self.assertTrue(db.execute("select to_regclass('aiops.acme_sandbox_attempts') "
                                       "is not null").fetchone()[0])
        attempt = 'ACME-SIM-NATIVE-RESTORE'
        run = self.post(attempt).json()['run_id']
        dump = '/usr/lib/postgresql/16/bin/pg_dump'
        restore = '/usr/lib/postgresql/16/bin/pg_restore'
        for binary in (dump, restore):
            self.assertIn('16.', subprocess.run([binary, '--version'], check=True,
                                               capture_output=True, text=True).stdout)
        target = 'aiops_core_acme_restore_ci'
        parsed = urlsplit(self.original)
        url = urlunsplit((parsed.scheme, parsed.netloc, '/' + target, '', ''))
        with psycopg.connect(self.original, autocommit=True) as admin:
            admin.execute(sql.SQL('create database {}').format(sql.Identifier(target)))
        try:
            with tempfile.TemporaryDirectory(prefix='core-acme-pg16-') as tmp:
                archive = Path(tmp) / 'sandbox.pgcustom'
                subprocess.run([dump, '--format=custom', '--no-owner', '--no-acl',
                                '--file=' + str(archive), '--dbname=' + self.url],
                               check=True, timeout=90, capture_output=True)
                self.assertRegex(hashlib.sha256(archive.read_bytes()).hexdigest(),
                                 r'^[0-9a-f]{64}$')
                subprocess.run([restore, '--no-owner', '--no-acl',
                                '--dbname=' + url, str(archive)],
                               check=True, timeout=90, capture_output=True)
            with psycopg.connect(url) as db:
                self.assertEqual(db.execute('select run_id from aiops.acme_sandbox_attempts '
                                            'where attempt_id=%s', (attempt,)).fetchone()[0], run)
                self.assertEqual(db.execute("select count(*) from aiops.run_events "
                                            "where run_id=%s and stage='SOURCE'",
                                            (run,)).fetchone()[0], 7)
        finally:
            with psycopg.connect(self.original, autocommit=True) as admin:
                admin.execute('select pg_terminate_backend(pid) from pg_stat_activity '
                              'where datname=%s and pid<>pg_backend_pid()', (target,))
                admin.execute(sql.SQL('drop database if exists {}').format(sql.Identifier(target)))

    def test_08_redacted_machine_receipt(self):
        attempt = 'ACME-SIM-RECEIPT'
        result = self.post(attempt).json()
        out = Path(os.environ['AIOPS_CORE_ACME_RECEIPT_DIR'])
        out.mkdir(parents=True, exist_ok=True)
        from unittest.mock import patch
        with patch.object(core, 'independent_readback',
                          side_effect=self._service_reads(result)):
            finalized = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(finalized.status_code, 200, finalized.text)
        result = finalized.json()
        first, second = self.get(attempt).json(), self.get(attempt).json()
        self.assertEqual(first, second)
        self.assertEqual(first['worker_receipt_sha256'], result['worker_receipt_sha256'])
        self.assertTrue(first['terminal_ticket_receipt_verified'])
        self.assertEqual(len(first['terminal_ticket_sha256']), 64)
        receipt = {'schema': 'aiops.core-acme-sandbox-pg16-ci.v2',
                   'source_head': os.environ['AIOPS_EXPECTED_HEAD_SHA'],
                   'migration_chain': [x[:3] for x in CHAIN],
                   'attempt_sha256': hashlib.sha256(attempt.encode()).hexdigest(),
                   'source_event_count': result['source_event_count'],
                   'evidence_count': result['evidence_count'],
                   'source_hashes_qualified': result['source_hashes_qualified'],
                   'incident_status': result['incident_status'],
                   'run_status': result['run_status'],
                   'ticket_authority': result['ticket_authority'],
                   'ticket_status': result['ticket_status'],
                   'analysis_kind': result['analysis_kind'],
                   'analysis_validated': result['analysis_validated'],
                   'critic_validated': result['critic_validated'],
                   'idempotent_replay': self.post(attempt).json()['idempotent'],
                   'terminal_receipt_sha256': result['worker_receipt_sha256'],
                   'terminal_ticket_sha256': result['terminal_ticket_sha256'],
                   'independent_final_reads': 2,
                   'ticket_transition_count': 2,
                   'worker_temporal_observed': False,
                   'human_glpi_attested': False, 'execution_allowed': False,
                   'effect_allowed': False, 'host_deployed': False,
                   'rollback': 'CODE_ONLY_KEEP_IMMUTABLE_013_TO_018'}
        receipt['payload_sha256'] = hashlib.sha256(json.dumps(
            receipt, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        p = out / 'core-acme-sandbox.json'
        p.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
        self.assertNotIn(TOKEN, p.read_text())

    def test_09_no_resolution_without_independent_worker_twin_policy(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-NO-PREMATURE-RESOLUTION'
        started = self.post(attempt).json()
        with patch.object(core, 'independent_readback',
                          side_effect=HTTPException(503, 'worker_unavailable')):
            response = self.client.post('/api/sandbox/acme/resolve',
                                        json=intent(attempt),
                                        headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(response.status_code, 503)
        state = self.get(attempt).json()
        self.assertEqual((state['incident_status'], state['run_status'],
                          state['ticket_status']),
                         ('PREPARED', 'PREPARED', 'PREPARED'))
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.run_events where run_id=%s "
                "and event_type='SIMULATED_RESOLVED'",
                (started['run_id'],)).fetchone()[0], 0)

    def _qualified_no_effect(self, state):
        common = {'attempt_id': state['attempt_id'], 'tenant_id': 'ACME-TEST',
                  'incident_id': state['incident_id'], 'run_id': state['run_id'],
                  'proposal_id': state['proposal_id']}
        flags = {'human_approved': False, 'execution_allowed': False,
                 'effect_allowed': False, 'live_effects_allowed': False,
                 'real_glpi_writes_allowed': False}
        approval = 'SIM-APP-TEST-VALID'
        worker = dict(common, **flags, approval_id=approval,
                      ticket_id=state['ticket_id'],
                      schema='aiops.worker-acme-simulated-no-effect.v1',
                      receipt_status='SIMULATED_NO_EFFECT',
                      receipt_phase='PRE_RESOLUTION',
                      core_status_at_validation='PREPARED',
                      resolution_verified=False, post_resolution_readback_required=True,
                      action='SIMULATE', effect_receipts=0,
                      approval_kind='SIMULATED', approval_issuer='TWIN_ACME_SIMULATED',
                      audit_authority='TEMPORAL_WORKFLOW_HISTORY_ONLY',
                      audit_transitions=['CORE_PREPARED_INDEPENDENTLY_VERIFIED',
                          'TWIN_SIMULATED_APPROVAL_VALIDATED',
                          'POLICY_SIMULATE_INDEPENDENTLY_VERIFIED', 'WORKER_NO_EFFECT'],
                      core_014_015_written=False, glpi_write=False)
        now = datetime.now(timezone.utc)
        twin = dict(common, **flags, approval_id=approval,
                    ticket_id=state['ticket_id'],
                    approval_kind='SIMULATED', approval_issuer='TWIN_ACME_SIMULATED',
                    core_status_at_issuance='PREPARED',
                    approval_phase='PRE_RESOLUTION', resolution_verified=False,
                    post_resolution_readback_required=True,
                    core_request_sha256=state['request_sha256'],
                    core_source_event_ids=state['source_event_ids'],
                    issuer_id='twin-acme-test', approval_actor='TWIN_ACME_SIMULATED',
                    approval_status='SIMULATED', approval_nonce='SIMNONCE-TEST-VALID',
                    issued_at=now.isoformat(),
                    expires_at=(now + timedelta(minutes=4)).isoformat())
        policy = dict(common, **flags, approval_id=approval,
                      ticket_id=state['ticket_id'], decision='SIMULATE',
                      state='PASS', mode='SIMULATION',
                      approval_kind='SIMULATED', approval_issuer='TWIN_ACME_SIMULATED')
        worker['core_request_sha256'] = state['request_sha256']
        worker['core_source_event_ids'] = state['source_event_ids']
        worker['twin_approval_nonce_sha256'] = hashlib.sha256(
            twin['approval_nonce'].encode('ascii')).hexdigest()
        worker['receipt_sha256'] = core.digest(worker)
        return [worker, twin, policy]

    def _service_reads(self, state):
        docs = dict(zip(('worker', 'twin', 'policy'),
                        self._qualified_no_effect(state)))
        return lambda component, attempt: docs[component]

    def test_10_core_only_finalization_after_independent_no_effect(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CORE-FINALIZE'
        state = self.post(attempt).json()
        with patch.object(core, 'independent_readback',
                          side_effect=self._service_reads(state)):
            result = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['incident_status'], 'RESOLVED')
        self.assertEqual(result.json()['run_status'], 'RESOLVED')
        self.assertEqual(result.json()['ticket_status'], 'RESOLVED')
        self.assertFalse(result.json()['effect_allowed'])
        self.assertEqual(self.get(attempt).json()['run_status'], 'RESOLVED')
        with patch.object(core, 'independent_readback',
                          side_effect=self._qualified_no_effect(state)):
            repeat = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertTrue(repeat.json()['idempotent'])
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.run_events where run_id=%s "
                "and event_type='SIMULATED_RESOLVED'",
                (state['run_id'],)).fetchone()[0], 1)

    def test_11_forged_human_worker_receipt_cannot_resolve(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CORE-FORGED-HUMAN'
        state = self.post(attempt).json()
        docs = self._qualified_no_effect(state)
        docs[0]['human_approved'] = True
        with patch.object(core, 'independent_readback', side_effect=lambda component, attempt: dict(zip(('worker', 'twin', 'policy'), docs))[component]):
            result = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(self.get(attempt).json()['run_status'], 'PREPARED')

    def test_12_immutable_ticket_digest_replay_after_restart(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-IMMUTABLE-TERMINAL'
        prepared = self.post(attempt).json()
        with patch.object(core, 'independent_readback',
                          side_effect=self._service_reads(prepared)):
            terminal = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(terminal.status_code, 200, terminal.text)
        sha = terminal.json()['worker_receipt_sha256']
        self.assertRegex(sha, r'^[0-9a-f]{64}$')
        self.assertTrue(terminal.json()['terminal_ticket_receipt_verified'])
        with psycopg.connect(self.url) as db:
            rows = db.execute(
                'select transition_seq,status,worker_receipt_sha256 '
                'from aiops.acme_sandbox_ticket_events where attempt_id=%s '
                'order by transition_seq', (attempt,)).fetchall()
            self.assertEqual([r[1] for r in rows], ['PREPARED', 'RESOLVED'])
            self.assertEqual(rows[1][2].strip(), sha)
            with self.assertRaises(psycopg.Error):
                with db.transaction():
                    db.execute("update aiops.acme_sandbox_ticket_events "
                               "set status='PREPARED' where attempt_id=%s "
                               "and transition_seq=2", (attempt,))
        app = FastAPI()
        app.include_router(core.router)
        with TestClient(app) as restarted:
            first = restarted.get('/api/sandbox/acme/e2e/' + attempt,
                                  headers={'Authorization': 'Bearer ' + TOKEN})
            second = restarted.get('/api/sandbox/acme/e2e/' + attempt,
                                   headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()['ticket_status'], 'RESOLVED')
        with patch.object(core, 'independent_readback',
                          side_effect=AssertionError('no Worker needed on durable replay')):
            repeat = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertTrue(repeat.json()['idempotent'])

    def test_13_foreign_tenant_and_digest_mismatch_fail_closed(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-DIGEST-FENCE'
        prepared = self.post(attempt).json()
        docs = dict(zip(('worker', 'twin', 'policy'),
                        self._qualified_no_effect(prepared)))
        docs['worker']['tenant_id'] = 'FOREIGN'
        with patch.object(core, 'independent_readback',
                          side_effect=lambda component, attempt: docs[component]):
            denied = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(self.get(attempt).json()['run_status'], 'PREPARED')
        with patch.object(core, 'independent_readback',
                          side_effect=self._service_reads(prepared)):
            accepted = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        with psycopg.connect(self.url) as db:
            db.execute("update aiops.run_events set payload=payload||%s::jsonb "
                       "where run_id=%s and event_type='SIMULATED_RESOLVED'",
                       (json.dumps({'worker_receipt_sha256': '0'*64}),
                        prepared['run_id']))
        self.assertEqual(self.get(attempt).status_code, 503)

    def test_14_concurrent_core_only_resolve_one_terminal_event(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CONCURRENT-RESOLVE'
        prepared = self.post(attempt).json()
        with patch.object(core, 'independent_readback',
                          side_effect=self._service_reads(prepared)):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: self.client.post(
                    '/api/sandbox/acme/resolve', json=intent(attempt),
                    headers={'Authorization': 'Bearer ' + TOKEN}), range(2)))
        self.assertEqual([r.status_code for r in results], [200, 200])
        self.assertEqual(sorted(r.json()['idempotent'] for r in results), [False, True])
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.acme_sandbox_ticket_events "
                "where attempt_id=%s and status='RESOLVED'",
                (attempt,)).fetchone()[0], 1)
            self.assertEqual(db.execute(
                "select count(*) from aiops.run_events "
                "where run_id=%s and event_type='SIMULATED_RESOLVED'",
                (prepared['run_id'],)).fetchone()[0], 1)

    def test_15_terminal_native_pg16_restore_and_018_rollback(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-TERMINAL-RESTORE'
        prepared = self.post(attempt).json()
        with patch.object(core, 'independent_readback',
                          side_effect=self._service_reads(prepared)):
            resolved = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(resolved.status_code, 200, resolved.text)
        with psycopg.connect(self.url) as db:
            db.execute('savepoint migration018_replay')
            db.execute((ROOT / 'db/migrations/018_acme_sandbox_ticket_terminal_receipts.sql').read_text())
            db.execute('rollback to savepoint migration018_replay')
            self.assertEqual(db.execute(
                "select count(*) from aiops.acme_sandbox_ticket_events "
                "where attempt_id=%s", (attempt,)).fetchone()[0], 2)
        target = 'aiops_core_acme_terminal_restore_ci'
        parsed = urlsplit(self.original)
        url = urlunsplit((parsed.scheme, parsed.netloc, '/' + target, '', ''))
        with psycopg.connect(self.original, autocommit=True) as admin:
            admin.execute(sql.SQL('create database {}').format(sql.Identifier(target)))
        try:
            with tempfile.TemporaryDirectory(prefix='core-acme-terminal-') as tmp:
                archive = Path(tmp) / 'terminal.pgcustom'
                subprocess.run(['/usr/lib/postgresql/16/bin/pg_dump',
                                '--format=custom', '--no-owner', '--no-acl',
                                '--file=' + str(archive), '--dbname=' + self.url],
                               check=True, timeout=90, capture_output=True)
                subprocess.run(['/usr/lib/postgresql/16/bin/pg_restore',
                                '--no-owner', '--no-acl', '--dbname=' + url,
                                str(archive)],
                               check=True, timeout=90, capture_output=True)
            old_url = os.environ['DATABASE_URL']
            try:
                os.environ['DATABASE_URL'] = url
                app = FastAPI()
                app.include_router(core.router)
                with TestClient(app) as restored:
                    a = restored.get('/api/sandbox/acme/e2e/' + attempt,
                                     headers={'Authorization': 'Bearer ' + TOKEN})
                    b = restored.get('/api/sandbox/acme/e2e/' + attempt,
                                     headers={'Authorization': 'Bearer ' + TOKEN})
                self.assertEqual(a.status_code, 200, a.text)
                self.assertEqual(a.json(), b.json())
                self.assertEqual(a.json()['worker_receipt_sha256'],
                                 resolved.json()['worker_receipt_sha256'])
                receipt_path = Path(os.environ['AIOPS_CORE_ACME_RECEIPT_DIR']) / 'core-acme-sandbox.json'
                evidence = json.loads(receipt_path.read_text())
                evidence.pop('payload_sha256')
                evidence['migration_018_savepoint_rollback'] = True
                evidence['native_pg16_terminal_restore'] = True
                evidence['restored_independent_final_reads'] = 2
                evidence['payload_sha256'] = hashlib.sha256(json.dumps(
                    evidence, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                receipt_path.write_text(json.dumps(evidence, sort_keys=True, indent=2))
            finally:
                os.environ['DATABASE_URL'] = old_url
        finally:
            with psycopg.connect(self.original, autocommit=True) as admin:
                admin.execute('select pg_terminate_backend(pid) from pg_stat_activity '
                              'where datname=%s and pid<>pg_backend_pid()', (target,))
                admin.execute(sql.SQL('drop database if exists {}').format(
                    sql.Identifier(target)))

    def test_16_stale_twin_and_service_credential_rotation_fail_closed(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-FRESHNESS-ROTATION'
        prepared = self.post(attempt).json()
        docs = dict(zip(('worker', 'twin', 'policy'),
                        self._qualified_no_effect(prepared)))
        docs['twin']['issued_at'] = (
            datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
        docs['twin']['expires_at'] = (
            datetime.now(timezone.utc) - timedelta(minutes=8)).isoformat()
        with patch.object(core, 'independent_readback',
                          side_effect=lambda component, attempt: docs[component]):
            denied = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(self.get(attempt).json()['ticket_status'], 'PREPARED')
        os.environ['AIOPS_INTERNAL_TOKEN'] = TOKEN + '-rotated'
        try:
            self.assertEqual(self.get(attempt).status_code, 401)
            self.assertEqual(self.post(attempt).status_code, 401)
        finally:
            os.environ['AIOPS_INTERNAL_TOKEN'] = TOKEN
        self.assertEqual(self.get(attempt).status_code, 200)

    def test_17_double_worker_receipt_rotation_no_mutation(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-WORKER-ROTATION'
        prepared = self.post(attempt).json()
        docs = dict(zip(('worker', 'twin', 'policy'),
                        self._qualified_no_effect(prepared)))
        calls = {'worker': 0}
        def changed(component, attempt_id):
            if component == 'worker':
                calls['worker'] += 1
                if calls['worker'] == 2:
                    return dict(docs['worker'], approval_id='SIM-APP-ROTATED')
            return docs[component]
        with patch.object(core, 'independent_readback', side_effect=changed):
            denied = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(self.get(attempt).json()['run_status'], 'PREPARED')
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.acme_sandbox_ticket_events "
                "where attempt_id=%s and status='RESOLVED'",
                (attempt,)).fetchone()[0], 0)

    def test_18_authenticated_service_origin_fence(self):
        """RG-ACME-18: reject foreign and malformed origins before bearer egress."""
        from unittest.mock import patch
        rejected = (
            'https://external.example:815',
            'http://aiops2-worker:9999',
            'http://169.254.169.254:815',
            'http://127.0.0.2:815',
            'http://aiops2-worker:abc',
            'http://aiops2-worker:99999',
            'http://[::1:815',
            'http://user:password@aiops2-worker:815',
            'http://aiops2-worker:815/unexpected',
            'http://aiops2-worker:815?token=unexpected',
        )
        for value in rejected:
            with self.subTest(origin=value):
                with patch.dict(os.environ, {'WORKER_URL': value}):
                    with patch.object(core.requests, 'get',
                                      side_effect=AssertionError('must not send bearer')) as get:
                        with self.assertRaises(HTTPException) as denied:
                            core.independent_readback('worker', 'ACME-SIM-ORIGIN-FENCE')
                        self.assertEqual(denied.exception.status_code, 503)
                        get.assert_not_called()

        class Response:
            status_code = 200
            content = b'{"sandbox":"synthetic"}'
            def json(self):
                return {'sandbox': 'synthetic'}

        for origin in ('http://aiops2-worker:815', 'http://127.0.0.1:815'):
            with self.subTest(allowed=origin):
                with patch.dict(os.environ, {'WORKER_URL': origin}):
                    with patch.object(core.requests, 'get', return_value=Response()) as get:
                        result = core.independent_readback('worker', 'ACME-SIM-ORIGIN-FENCE')
                        self.assertEqual(result, {'sandbox': 'synthetic'})
                        self.assertEqual(get.call_count, 1)
                        self.assertFalse(get.call_args.kwargs['allow_redirects'])
                        self.assertEqual(get.call_args.kwargs['timeout'], 5)

    def test_19_rg_acme_19_worker_ticket_and_post_lock_freshness(self):
        """RG-ACME-19: receipt ticket binding and lock-wait TTL are mandatory."""
        from unittest.mock import patch
        foreign_attempt = 'ACME-SIM-WORKER-TICKET-FENCE'
        foreign = self.post(foreign_attempt).json()
        docs = dict(zip(('worker', 'twin', 'policy'),
                        self._qualified_no_effect(foreign)))
        docs['worker']['ticket_id'] = 'SIM-GLPI-FOREIGN-TICKET'
        docs['worker']['receipt_sha256'] = core.digest({
            k: v for k, v in docs['worker'].items() if k != 'receipt_sha256'})
        with patch.object(core, 'independent_readback',
                          side_effect=lambda component, attempt: docs[component]):
            denied = self.client.post('/api/sandbox/acme/resolve',
                json=intent(foreign_attempt),
                headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(self.get(foreign_attempt).json()['ticket_status'], 'PREPARED')

        attempt = 'ACME-SIM-POSTLOCK-EXPIRY'
        prepared = self.post(attempt).json()
        original_fresh = core.approval_fresh
        checks = []
        def freshness(twin):
            checks.append(len(checks) + 1)
            if len(checks) == 2:
                raise HTTPException(503, 'sandbox_approval_expired_after_lock')
            return original_fresh(twin)
        with patch.object(core, 'independent_readback',
                          side_effect=self._service_reads(prepared)):
            with patch.object(core, 'approval_fresh', side_effect=freshness):
                denied = self.client.post('/api/sandbox/acme/resolve',
                    json=intent(attempt),
                    headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(checks, [1, 2])
        self.assertEqual(self.get(attempt).json()['run_status'], 'PREPARED')
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.acme_sandbox_ticket_events "
                "where attempt_id=%s and status='RESOLVED'",
                (attempt,)).fetchone()[0], 0)

if __name__ == '__main__':
    unittest.main()
