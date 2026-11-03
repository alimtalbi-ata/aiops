"""Disposable PG16 Core ACME sandbox, zero GLPI/LIVE/host effects."""
import concurrent.futures
import hashlib
from datetime import datetime, timedelta, timezone
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
         '018_acme_sandbox_terminal_ticket_receipt.sql',
    '019_acme_sandbox_twin_topology.sql']

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
        receipt = {'schema': 'aiops.core-acme-sandbox-pg16-ci.v1',
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
                   'human_glpi_attested': False, 'execution_allowed': False,
                   'effect_allowed': False, 'host_deployed': False,
                   'rollback': 'CODE_ONLY_KEEP_IMMUTABLE_013_014_015_016'}
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
                      ticket_id=state['ticket_id'], schema='aiops.worker-acme-simulated-no-effect.v1',
                      receipt_status='SIMULATED_NO_EFFECT',
                      receipt_phase='PRE_RESOLUTION',
                      core_status_at_validation='PREPARED',
                      resolution_verified=False, post_resolution_readback_required=True,
                      action='SIMULATE', effect_receipts=0,
                      core_014_015_written=False, glpi_write=False,
                      audit_authority='TEMPORAL_WORKFLOW_HISTORY_ONLY',
                      audit_transitions=[
                          'CORE_PREPARED_INDEPENDENTLY_VERIFIED',
                          'TWIN_SIMULATED_APPROVAL_VALIDATED',
                          'POLICY_SIMULATE_INDEPENDENTLY_VERIFIED',
                          'WORKER_NO_EFFECT'],
                      approval_kind='SIMULATED', approval_issuer='TWIN_ACME_SIMULATED')
        twin = dict(common, **flags, approval_id=approval,
                    ticket_id=state['ticket_id'],
                    approval_kind='SIMULATED', approval_issuer='TWIN_ACME_SIMULATED',
                    core_status_at_issuance='PREPARED')
        policy = dict(common, **flags, approval_id=approval,
                      ticket_id=state['ticket_id'], decision='SIMULATE',
                      approval_kind='SIMULATED', approval_issuer='TWIN_ACME_SIMULATED')
        nonce = 'SIM-NONCE-CORE-TEST-' + state['attempt_id']
        issued = datetime.now(timezone.utc) - timedelta(seconds=10)
        twin.update(approval_nonce=nonce, approval_phase='PRE_RESOLUTION',
                    approval_status='SIMULATED',
                    core_request_sha256=state['request_sha256'],
                    core_source_event_ids=state['source_event_ids'],
                    issued_at=issued.isoformat(),
                    expires_at=(issued + timedelta(minutes=5)).isoformat())
        worker.update(core_request_sha256=state['request_sha256'],
                      core_source_event_ids=state['source_event_ids'],
                      twin_approval_nonce_sha256=hashlib.sha256(
                          nonce.encode('ascii')).hexdigest())
        worker['receipt_sha256'] = core.digest(worker)
        return [worker, twin, policy]

    def test_10_core_only_finalization_after_independent_no_effect(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CORE-FINALIZE'
        state = self.post(attempt).json()
        with patch.object(core, 'independent_readback',
                          side_effect=self._qualified_no_effect(state)):
            result = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['incident_status'], 'RESOLVED')
        self.assertEqual(result.json()['run_status'], 'RESOLVED')
        self.assertEqual(result.json()['ticket_status'], 'RESOLVED')
        self.assertFalse(result.json()['effect_allowed'])
        self.assertEqual(self.get(attempt).json()['run_status'], 'RESOLVED')
        # A replay must NOT depend on expiring Twin/Worker HTTP authorities.
        with patch.object(core, 'independent_readback',
                          side_effect=AssertionError('replay_must_be_local')):
            repeat = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertTrue(repeat.json()['idempotent'])
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.run_events where run_id=%s "
                "and event_type='SIMULATED_RESOLVED'",
                (state['run_id'],)).fetchone()[0], 1)
            terminal = db.execute(
                'select ticket_status,worker_receipt_sha256,worker_receipt,'
                'terminal_ticket_sha256 from aiops.acme_sandbox_terminal_tickets '
                'where tenant_id=%s and attempt_id=%s',
                ('ACME-TEST',attempt)).fetchone()
            self.assertEqual(terminal[0], 'RESOLVED')
            self.assertEqual(terminal[1].strip(), terminal[2]['receipt_sha256'])
            self.assertEqual(terminal[1].strip(), core.digest({
                k:v for k,v in terminal[2].items() if k != 'receipt_sha256'}))
            self.assertEqual(terminal[3].strip(),
                             result.json()['terminal_ticket_sha256'])
            self.assertEqual(db.execute(
                "select ticket_status from aiops.acme_sandbox_attempts "
                "where attempt_id=%s",(attempt,)).fetchone()[0], 'PREPARED')

    def test_11_forged_human_worker_receipt_cannot_resolve(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CORE-FORGED-HUMAN'
        state = self.post(attempt).json()
        docs = self._qualified_no_effect(state)
        docs[0]['human_approved'] = True
        docs[0]['receipt_sha256'] = core.digest({
            k:v for k,v in docs[0].items() if k != 'receipt_sha256'})
        with patch.object(core, 'independent_readback', side_effect=docs):
            result = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(self.get(attempt).json()['run_status'], 'PREPARED')


    def test_12_reject_worker_receipt_digest_mismatch(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CORE-BAD-DIGEST'
        state = self.post(attempt).json()
        docs = self._qualified_no_effect(state)
        docs[0]['receipt_sha256'] = '0' * 64
        with patch.object(core, 'independent_readback', side_effect=docs):
            response = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.get(attempt).json()['ticket_status'], 'PREPARED')

    def test_13_terminal_ticket_is_independent_and_immutable(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CORE-TERMINAL-IMMUTABLE'
        state = self.post(attempt).json()
        with patch.object(core, 'independent_readback',
                          side_effect=self._qualified_no_effect(state)):
            self.assertEqual(self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN}).status_code, 200)
        with psycopg.connect(self.url) as db:
            with self.assertRaises(psycopg.Error):
                with db.transaction():
                    db.execute("update aiops.acme_sandbox_terminal_tickets "
                               "set ticket_status='PREPARED' where attempt_id=%s",
                               (attempt,))
            with self.assertRaises(psycopg.Error):
                with db.transaction():
                    db.execute("delete from aiops.acme_sandbox_terminal_tickets "
                               "where attempt_id=%s", (attempt,))
        self.assertEqual(self.get(attempt).json()['ticket_status'], 'RESOLVED')

    def test_14_stale_twin_approval_denies_terminal_write(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CORE-STALE-TWIN'
        state = self.post(attempt).json()
        docs = self._qualified_no_effect(state)
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        docs[1]['issued_at'] = past.isoformat()
        docs[1]['expires_at'] = (past + timedelta(minutes=5)).isoformat()
        with patch.object(core, 'independent_readback', side_effect=docs):
            response = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.get(attempt).json()['run_status'], 'PREPARED')

    def test_15_native_pg16_terminal_backup_restore(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-TERMINAL-RESTORE'
        state = self.post(attempt).json()
        with patch.object(core, 'independent_readback',
                          side_effect=self._qualified_no_effect(state)):
            self.assertEqual(self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN}).status_code, 200)
        target = 'aiops_core_acme_terminal_restore_ci'
        parsed = urlsplit(self.original)
        url = urlunsplit((parsed.scheme, parsed.netloc, '/' + target, '', ''))
        with psycopg.connect(self.original, autocommit=True) as admin:
            admin.execute(sql.SQL('create database {}').format(sql.Identifier(target)))
        try:
            with tempfile.TemporaryDirectory(prefix='acme-terminal-restore-') as tmp:
                archive = Path(tmp) / 'terminal.pgcustom'
                subprocess.run(['/usr/lib/postgresql/16/bin/pg_dump',
                    '--format=custom','--no-owner','--no-acl',
                    '--file='+str(archive),'--dbname='+self.url],
                    check=True,timeout=90,capture_output=True)
                subprocess.run(['/usr/lib/postgresql/16/bin/pg_restore',
                    '--no-owner','--no-acl','--dbname='+url,str(archive)],
                    check=True,timeout=90,capture_output=True)
            with psycopg.connect(url) as db:
                row = db.execute(
                    'select ticket_status,worker_receipt_sha256,worker_receipt '
                    'from aiops.acme_sandbox_terminal_tickets where attempt_id=%s',
                    (attempt,)).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], 'RESOLVED')
                self.assertEqual(row[1].strip(), row[2]['receipt_sha256'])
                self.assertEqual(db.execute(
                    'select status from aiops.runs where run_id=%s',
                    (state['run_id'],)).fetchone()[0], 'RESOLVED')
        finally:
            with psycopg.connect(self.original, autocommit=True) as admin:
                admin.execute('select pg_terminate_backend(pid) from pg_stat_activity '
                              'where datname=%s and pid<>pg_backend_pid()', (target,))
                admin.execute(sql.SQL('drop database if exists {}').format(
                    sql.Identifier(target)))


    def test_16_forged_worker_glpi_write_denied_even_with_valid_digest(self):
        from unittest.mock import patch
        attempt = 'ACME-SIM-CORE-FORGED-GLPI'
        state = self.post(attempt).json()
        docs = self._qualified_no_effect(state)
        docs[0]['glpi_write'] = True
        docs[0]['receipt_sha256'] = core.digest({
            k:v for k,v in docs[0].items() if k != 'receipt_sha256'})
        with patch.object(core, 'independent_readback', side_effect=docs):
            response = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.get(attempt).json()['ticket_status'], 'PREPARED')


    def test_17_registered_temporal_worker_same_pg16_run(self):
        """RG-ACME-21: real PG16 + registered Temporal activity, synthetic Twin/Policy.

        This is disposable CI integration, not Debian E2E or human GLPI authority.
        """
        import asyncio
        from copy import deepcopy
        from unittest.mock import patch
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from worker.workflow import AcmeSimulatedHitlWorkflow
        from worker import main as worker_main
        from worker.acme_simulated_hitl import receipt_digest_valid
        from test_worker_acme_simulated_hitl import fixtures, INTENT

        attempt = 'ACME-SIM-PG16-TEMPORAL-001'
        response = self.post(attempt)
        self.assertEqual(response.status_code, 200, response.text)
        state = self.get(attempt).json()
        self.assertEqual(state['run_status'], 'PREPARED')
        docs = fixtures()
        approval = 'SIM-APP-PG16-TEMPORAL-001'
        worker_intent = dict(INTENT, attempt_id=attempt,
                             idempotency_key=attempt,
                             incident_id=state['incident_id'],
                             run_id=state['run_id'],
                             proposal_id=state['proposal_id'],
                             ticket_id=state['ticket_id'],
                             approval_id=approval)
        docs['core'] = deepcopy(state)
        for component in ('twin', 'policy'):
            docs[component].update({
                k: worker_intent[k] for k in (
                    'attempt_id', 'tenant_id', 'incident_id', 'run_id',
                    'proposal_id', 'ticket_id', 'approval_id')})
        now = datetime.now(timezone.utc)
        docs['twin'].update(
            core_request_sha256=state['request_sha256'],
            core_source_event_ids=state['source_event_ids'],
            approval_nonce='SIMNONCE-PG16-TEMPORAL-001',
            issued_at=(now - timedelta(seconds=10)).isoformat(),
            expires_at=(now + timedelta(minutes=3)).isoformat())

        reads = []
        class Response:
            def __init__(self, payload):
                self.status_code = 200
                self._payload = payload
                self.content = json.dumps(payload).encode()
            def json(self):
                return deepcopy(self._payload)

        def fake_get(url, **kwargs):
            component = next((key for key, origin in (
                ('core', worker_main.CORE), ('twin', worker_main.TWIN),
                ('policy', worker_main.POLICY))
                if url == origin.rstrip('/') + '/api/sandbox/acme/e2e/' + attempt), None)
            self.assertIsNotNone(component)
            self.assertEqual(kwargs.get('allow_redirects'), False)
            reads.append(component)
            if component == 'core':
                actual = self.get(attempt)
                self.assertEqual(actual.status_code, 200)
                return Response(actual.json())
            return Response(docs[component])

        async def run_temporal():
            async with await WorkflowEnvironment.start_time_skipping() as env:
                async with Worker(env.client, task_queue='acme-pg16-joined',
                                  workflows=[AcmeSimulatedHitlWorkflow],
                                  activities=[worker_main.acme_simulated_no_effect]):
                    return await env.client.execute_workflow(
                        AcmeSimulatedHitlWorkflow.run, worker_intent,
                        id='acme-pg16-joined-' + attempt,
                        task_queue='acme-pg16-joined')

        with patch.object(worker_main.requests, 'get', side_effect=fake_get):
            worker_receipt = asyncio.run(run_temporal())
        self.assertEqual(reads, ['core','twin','policy'] * 2)
        self.assertTrue(receipt_digest_valid(worker_receipt))
        self.assertEqual(worker_receipt['receipt_status'], 'SIMULATED_NO_EFFECT')
        self.assertEqual(worker_receipt['run_id'], state['run_id'])
        self.assertEqual(worker_receipt['effect_receipts'], 0)
        self.assertFalse(worker_receipt['human_approved'])
        self.assertFalse(worker_receipt['live_effects_allowed'])
        with patch.object(core, 'independent_readback',
                          side_effect=[worker_receipt, docs['twin'], docs['policy']]):
            terminal = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(terminal.status_code, 200, terminal.text)
        resolved = terminal.json()
        self.assertEqual(resolved['run_status'], 'RESOLVED')
        self.assertEqual(resolved['incident_status'], 'RESOLVED')
        self.assertEqual(resolved['ticket_status'], 'RESOLVED')
        self.assertEqual(resolved['worker_receipt_sha256'], worker_receipt['receipt_sha256'])
        self.assertEqual(self.get(attempt).json()['terminal_ticket_sha256'],
                         resolved['terminal_ticket_sha256'])
        with psycopg.connect(self.url) as db:
            persisted = db.execute(
                'select worker_receipt_sha256,ticket_status from '
                'aiops.acme_sandbox_terminal_tickets where attempt_id=%s',
                (attempt,)).fetchone()
            self.assertEqual(persisted[0].strip(), worker_receipt['receipt_sha256'])
            self.assertEqual(persisted[1], 'RESOLVED')
        evidence = {
            'schema': 'aiops.acme-pg16-temporal-joined-ci.v1',
            'source_head': os.environ['AIOPS_EXPECTED_HEAD_SHA'],
            'tenant_id': 'ACME-TEST', 'attempt_id': attempt,
            'incident_id': state['incident_id'], 'run_id': state['run_id'],
            'ticket_id': state['ticket_id'], 'approval_id': approval,
            'worker_receipt_sha256': worker_receipt['receipt_sha256'],
            'terminal_ticket_sha256': resolved['terminal_ticket_sha256'],
            'pg16_terminal_readback': 'RESOLVED',
            'registered_temporal_activity': True, 'worker_readback_count': len(reads),
            'twin_policy_authorities': 'SYNTHETIC_CI_FIXTURES',
            'human_glpi_attested': False, 'live_effects': 0,
            'debian_host_deployed': False, 'release_stable': 'NO_GO'
        }
        out = Path('/tmp/acme-pg16-temporal-joined.json')
        out.write_text(json.dumps(evidence, sort_keys=True, separators=(',', ':')))
        self.assertEqual(json.loads(out.read_text())['run_id'], state['run_id'])


    def test_18_real_pg16_acme_twin_san_path_is_isolated(self):
        """RG-ACME-22: two FC fabrics, RHEL multipath, payments/ERP synthetic only."""
        from unittest.mock import patch
        from twin import acme_sandbox as twin
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                "select count(*) from aiops.twin_nodes "
                "where site='ACME-TEST-SIMULATION'").fetchone()[0],9)
            self.assertEqual(db.execute(
                "select count(*) from aiops.twin_edges "
                "where edge_id like 'ACME-TEST-SIM-EDGE-%'").fetchone()[0],8)
        with patch.dict(os.environ,{'AIOPS_ACME_TWIN_APPROVAL_KEY':'a'*64}):
            impacted=twin.sourced_impact()
            self.assertIn('ACME-TEST-SAN-FABRIC-A',impacted)
            self.assertIn('ACME-TEST-HOST-RHEL-MPATH-01',impacted)
            self.assertIn('ACME-TEST-SVC-PAYMENTS',impacted)
            self.assertIn('ACME-TEST-SVC-ERP',impacted)
            self.assertEqual(twin.capabilities()['component'],'twin')

    def test_19_mixed_live_twin_graph_refused_and_cleaned(self):
        """RG-ACME-23: never let simulated approval traverse a real CMDB node."""
        from fastapi import HTTPException
        from twin import acme_sandbox as twin
        with psycopg.connect(self.url) as db:
            db.execute(
                "insert into aiops.twin_nodes(node_id,type,name,site,state) "
                "values('FOREIGN-LIVE-CI-TEST','SERVER','foreign test','LIVE','UNKNOWN')")
            db.execute(
                "insert into aiops.twin_edges "
                "(edge_id,source_id,target_id,relation_type,confidence) "
                "values('ACME-TEST-SIM-EDGE-FOREIGN-CI','ACME-TEST-SAN-FABRIC-A',"
                "'FOREIGN-LIVE-CI-TEST','SIMULATED_DEPENDS_ON',1.0)")
        try:
            with self.assertRaises(HTTPException) as caught:
                twin.sourced_impact()
            self.assertEqual(caught.exception.status_code,503)
        finally:
            with psycopg.connect(self.url) as db:
                db.execute("delete from aiops.twin_edges "
                           "where edge_id='ACME-TEST-SIM-EDGE-FOREIGN-CI'")
                db.execute("delete from aiops.twin_nodes "
                           "where node_id='FOREIGN-LIVE-CI-TEST'")
        self.assertIn('ACME-TEST-SVC-PAYMENTS',twin.sourced_impact())

    def test_20_rg_acme_18_direct_origin_and_proxy_fence(self):
        """RG-ACME-18: no bearer egress to malformed or foreign origins."""
        from unittest.mock import patch
        rejected = ('https://external.example:815', 'http://aiops2-worker:9999',
                    'http://169.254.169.254:815', 'http://127.0.0.2:815',
                    'http://aiops2-worker:abc', 'http://aiops2-worker:99999',
                    'http://[::1:815', 'http://user:pass@aiops2-worker:815',
                    'http://aiops2-worker:815/unexpected',
                    'http://aiops2-worker:815?token=unexpected')
        for origin in rejected:
            with self.subTest(origin=origin):
                with patch.dict(os.environ, {'WORKER_URL': origin}):
                    with patch.object(core.requests, 'Session') as make:
                        with self.assertRaises(HTTPException) as denied:
                            core.independent_readback('worker', 'ACME-SIM-ORIGIN-FENCE')
                        self.assertEqual(denied.exception.status_code, 503)
                        make.assert_not_called()

        class Response:
            status_code = 200
            content = b'{"sandbox":"synthetic"}'
            def json(self):
                return {'sandbox': 'synthetic'}

        for origin in ('http://aiops2-worker:815', 'http://127.0.0.1:815'):
            with self.subTest(allowed=origin):
                with patch.dict(os.environ, {
                        'WORKER_URL': origin, 'HTTP_PROXY': 'http://hostile.example:3128',
                        'HTTPS_PROXY': 'http://hostile.example:3128',
                        'ALL_PROXY': 'http://hostile.example:3128',
                        'NETRC': '/tmp/hostile-netrc-do-not-read'}):
                    with patch.object(core.requests, 'Session') as make:
                        session = make.return_value
                        session.get.return_value = Response()
                        self.assertEqual(
                            core.independent_readback('worker', 'ACME-SIM-ORIGIN-FENCE'),
                            {'sandbox': 'synthetic'})
                        self.assertIs(session.trust_env, False)
                        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
                        self.assertEqual(session.get.call_args.kwargs['timeout'], 5)
                        self.assertEqual(
                            session.get.call_args.kwargs['headers']['Authorization'],
                            'Bearer ' + TOKEN)
                        session.close.assert_called_once()

    def test_21_rg_acme_19_worker_ticket_and_post_lock_expiry(self):
        """RG-ACME-19: digest cannot rebind ticket or outlive PG16 lock wait."""
        from unittest.mock import patch
        attempt = 'ACME-SIM-WORKER-TICKET-REBOUND'
        prepared = self.post(attempt).json()
        docs = self._qualified_no_effect(prepared)
        docs[0]['ticket_id'] = 'SIM-GLPI-FOREIGN-TICKET'
        docs[0]['receipt_sha256'] = core.digest({
            k: v for k, v in docs[0].items() if k != 'receipt_sha256'})
        with patch.object(core, 'independent_readback', side_effect=docs):
            denied = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(self.get(attempt).json()['ticket_status'], 'PREPARED')

        # RG-ACME-19: new terminal writes cannot omit the canonical ticket.
        attempt_missing = 'ACME-SIM-WORKER-TICKET-MISSING'
        prepared_missing = self.post(attempt_missing).json()
        missing = self._qualified_no_effect(prepared_missing)
        missing[0].pop('ticket_id')
        missing[0]['receipt_sha256'] = core.digest({
            k: v for k, v in missing[0].items() if k != 'receipt_sha256'})
        with patch.object(core, 'independent_readback', side_effect=missing):
            denied_missing = self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt_missing),
                headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(denied_missing.status_code, 503)
        self.assertEqual(self.get(attempt_missing).json()['run_status'], 'PREPARED')

        # Existing append-only pre-RG-19 terminal rows had Worker v1 receipts
        # without ticket_id; read-only historical replay must remain possible.
        ticket = prepared['ticket_id']
        self.assertTrue(core.terminal_ticket_readback_bound({}, ticket))
        self.assertTrue(core.terminal_ticket_readback_bound({'ticket_id': ticket}, ticket))
        self.assertFalse(core.terminal_ticket_readback_bound(
            {'ticket_id': 'SIM-GLPI-FOREIGN-TICKET'}, ticket))
        self.assertFalse(core.terminal_ticket_readback_bound({'ticket_id': None}, ticket))

        attempt = 'ACME-SIM-APPROVAL-LOCK-EXPIRED'
        prepared = self.post(attempt).json()
        original = core.approval_fresh
        checks = []
        def expire_on_second(issued, expires):
            checks.append(len(checks) + 1)
            if len(checks) == 2:
                raise HTTPException(503, 'sandbox_twin_approval_expired_after_lock')
            return original(issued, expires)
        with patch.object(core, 'independent_readback',
                          side_effect=self._qualified_no_effect(prepared)):
            with patch.object(core, 'approval_fresh', side_effect=expire_on_second):
                denied = self.client.post('/api/sandbox/acme/resolve',
                    json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(checks, [1, 2])
        self.assertEqual(self.get(attempt).json()['run_status'], 'PREPARED')
        with psycopg.connect(self.url) as db:
            self.assertEqual(db.execute(
                'select count(*) from aiops.acme_sandbox_terminal_tickets '
                'where attempt_id=%s', (attempt,)).fetchone()[0], 0)


    def test_22_rg_acme_28_concurrent_terminal_join_and_independent_reads(self):
        """RG-ACME-28: concurrent terminal admission creates exactly one immutable ticket."""
        from unittest.mock import patch
        attempt = 'ACME-SIM-TERMINAL-CONCURRENT-RG28'
        prepared = self.post(attempt).json()
        worker, twin, policy = self._qualified_no_effect(prepared)
        documents = {'worker': worker, 'twin': twin, 'policy': policy}
        calls = []

        def independent(component, observed_attempt):
            self.assertEqual(observed_attempt, attempt)
            calls.append(component)
            return documents[component]

        def resolve_once(_):
            return self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})

        with patch.object(core, 'independent_readback', side_effect=independent):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(resolve_once, range(2)))
        self.assertEqual([r.status_code for r in replies], [200, 200],
                         [r.text for r in replies])
        self.assertEqual(sorted(r.json()['idempotent'] for r in replies),
                         [False, True])
        for reply in replies:
            self.assertEqual(reply.json()['ticket_status'], 'RESOLVED')
            self.assertEqual(reply.json()['run_id'], prepared['run_id'])
        first = self.get(attempt)
        restarted = FastAPI()
        restarted.include_router(core.router)
        with TestClient(restarted) as new_client:
            second = new_client.get('/api/sandbox/acme/e2e/' + attempt,
                headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        for field in ('incident_id', 'run_id', 'ticket_id', 'worker_receipt_sha256',
                      'terminal_ticket_sha256', 'ticket_status'):
            self.assertEqual(first.json()[field], second.json()[field])
        with psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute(
                'select count(*) from aiops.acme_sandbox_terminal_tickets '
                'where tenant_id=%s and attempt_id=%s',
                ('ACME-TEST', attempt)).fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "select count(*) from aiops.run_events where run_id=%s "
                "and event_type='SIMULATED_RESOLVED'",
                (prepared['run_id'],)).fetchone()[0], 1)

    def test_23_rg_acme_29_abstain_refuse_reopen_fail_closed(self):
        """RG-ACME-29: abstain/refuse/revoke never create terminal authority."""
        from unittest.mock import patch
        cases = [
            ('POLICY-ABSTAIN', 'policy', 'decision', 'ABSTAIN'),
            ('POLICY-DENY', 'policy', 'decision', 'DENY'),
            ('WORKER-REFUSED', 'worker', 'receipt_status', 'REFUSED'),
            ('TWIN-REVOKED', 'twin', 'approval_status', 'REVOKED'),
        ]
        for suffix, component, field, value in cases:
            with self.subTest(case=suffix):
                attempt = 'ACME-SIM-RG29-' + suffix
                prepared = self.post(attempt).json()
                docs = self._qualified_no_effect(prepared)
                selected = {'worker': 0, 'twin': 1, 'policy': 2}[component]
                docs[selected][field] = value
                if component == 'worker':
                    docs[0]['receipt_sha256'] = core.digest({
                        k: v for k, v in docs[0].items()
                        if k != 'receipt_sha256'})
                with patch.object(core, 'independent_readback', side_effect=docs):
                    denied = self.client.post('/api/sandbox/acme/resolve',
                        json=intent(attempt),
                        headers={'Authorization': 'Bearer ' + TOKEN})
                self.assertEqual(denied.status_code, 503, denied.text)
                actual = self.get(attempt)
                self.assertEqual(actual.status_code, 200, actual.text)
                self.assertEqual(
                    (actual.json()['incident_status'], actual.json()['run_status'],
                     actual.json()['ticket_status']),
                    ('PREPARED', 'PREPARED', 'PREPARED'))
                with psycopg.connect(self.url) as conn:
                    self.assertEqual(conn.execute(
                        'select count(*) from aiops.acme_sandbox_terminal_tickets '
                        'where attempt_id=%s', (attempt,)).fetchone()[0], 0)
                    self.assertEqual(conn.execute(
                        "select count(*) from aiops.run_events where run_id=%s "
                        "and event_type='SIMULATED_RESOLVED'",
                        (prepared['run_id'],)).fetchone()[0], 0)

        # REOPENED is not an authorized Core sandbox transition in migration 017.
        attempt = 'ACME-SIM-RG29-REOPEN'
        prepared = self.post(attempt).json()
        with psycopg.connect(self.url) as conn:
            with self.assertRaises(psycopg.Error):
                with conn.transaction():
                    conn.execute("update aiops.incidents set state='REOPENED' "
                                 "where incident_id=%s", (prepared['incident_id'],))
            with self.assertRaises(psycopg.Error):
                with conn.transaction():
                    conn.execute("update aiops.runs set status='REOPENED' "
                                 "where run_id=%s", (prepared['run_id'],))
        self.assertEqual(self.get(attempt).json()['run_status'], 'PREPARED')



    def test_24_rg_acme_30_real_pg16_lock_wait_rechecks_freshness(self):
        """RG-ACME-30: real PG16 lock contention fences post-read terminal writes."""
        import threading
        from unittest.mock import patch
        attempt = 'ACME-SIM-RG30-REAL-LOCK-WAIT'
        prepared = self.post(attempt).json()
        worker, twin, policy = self._qualified_no_effect(prepared)
        documents = {'worker': worker, 'twin': twin, 'policy': policy}
        at_policy = threading.Event()
        allow_policy = threading.Event()
        first_fresh = threading.Event()
        second_fresh = threading.Event()
        checks = []
        original_fresh = core.approval_fresh

        def independent(component, observed_attempt):
            self.assertEqual(observed_attempt, attempt)
            if component == 'policy':
                at_policy.set()
                if not allow_policy.wait(10):
                    raise AssertionError('policy readback gate timed out')
            return documents[component]

        def fresh_under_lock(issued, expires):
            checks.append(len(checks) + 1)
            if len(checks) == 1:
                original_fresh(issued, expires)
                first_fresh.set()
            else:
                second_fresh.set()
                raise HTTPException(503, 'sandbox_twin_approval_expired_after_lock')

        def resolve_once():
            return self.client.post('/api/sandbox/acme/resolve',
                json=intent(attempt), headers={'Authorization': 'Bearer ' + TOKEN})

        with patch.object(core, 'independent_readback', side_effect=independent):
            with patch.object(core, 'approval_fresh', side_effect=fresh_under_lock):
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(resolve_once)
                    try:
                        self.assertTrue(at_policy.wait(10))
                        with psycopg.connect(self.url) as blocker:
                            with blocker.transaction():
                                blocker.execute(
                                    'select pg_advisory_xact_lock(hashtextextended(%s,0))',
                                    ('core-acme-sandbox:ACME-TEST:' + attempt,))
                                allow_policy.set()
                                self.assertTrue(first_fresh.wait(10))
                                # The second freshness check must not run
                                # before the real PostgreSQL lock is released.
                                self.assertFalse(second_fresh.wait(0.2))
                        denied = future.result(timeout=10)
                    finally:
                        allow_policy.set()
        self.assertEqual(denied.status_code, 503, denied.text)
        self.assertEqual(checks, [1, 2])
        self.assertEqual(self.get(attempt).json()['ticket_status'], 'PREPARED')
        with psycopg.connect(self.url) as conn:
            self.assertEqual(conn.execute(
                'select count(*) from aiops.acme_sandbox_terminal_tickets '
                'where tenant_id=%s and attempt_id=%s',
                ('ACME-TEST', attempt)).fetchone()[0], 0)
            self.assertEqual(conn.execute(
                "select count(*) from aiops.run_events where run_id=%s "
                "and event_type='SIMULATED_RESOLVED'",
                (prepared['run_id'],)).fetchone()[0], 0)

if __name__ == '__main__':
    unittest.main()
