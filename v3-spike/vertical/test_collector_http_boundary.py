"""Actual HTTP/SQLite and boundary code; downstream handler/graph/publisher fixtures."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
import http.client
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import unittest
from collector_admission_fence import initialize, provision
from authority_restore_guard_candidate import provision_witness, snapshot
from collector_http_boundary import dispatch, ADMIT, RECEIPT
from collector_receipt import digest
from continuous_collector import batch
from ingestion_demo import ingest
from test_collector_transition import response_for, persisted_fixture
from test_collector_admission_service import GraphFixture
from test_fenced_durable_collector import serve


class BoundaryTests(unittest.TestCase):
    def test_strict_fenced_ingress(self):
        self.exercise()

    def test_guarded_publication_failure(self):
        self.exercise(fail_publish=True)

    def exercise(self, *, fail_publish=False):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'authority.db'
            witness_path = Path(tmp) / 'witness.db'
            old_path = Path(tmp) / 'old.db'
            scope = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-one')
            token = secrets.token_hex(32)
            with closing(sqlite3.connect(path)) as db:
                initialize(db)
                provision(db, scope, token)
                with closing(sqlite3.connect(witness_path)) as witness, closing(sqlite3.connect(old_path)) as old:
                    provision_witness(db, witness)
                    db.backup(old)
            now = datetime.now(timezone.utc)
            windows = [{'at': (now - timedelta(seconds=age)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'median': value, 'samples': [value] * 5} for age, value in ((10, 10), (2, 100))]
            rows = batch(*windows)
            data = {'generation': 0, 'rows': rows}
            calls, delegated = [], []
            guard = False
            active_path = path
            active_witness = witness_path
            readbacks = {}

            def publisher(records):
                calls.append(records)
                with closing(sqlite3.connect(path)) as db, closing(sqlite3.connect(witness_path)) as witness:
                    self.assertEqual(db.execute('SELECT state FROM collector_fence').fetchone()[0], 'PENDING')
                    self.assertEqual(witness.execute('SELECT state FROM guard').fetchone()[0], 'BUSY')
                if fail_publish:
                    raise OSError('synthetic publication uncertainty')
                core, context = persisted_fixture(records)
                readbacks[core['run']['run_id']] = (core, context)
                return response_for(records)['publication']

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def reply(self, status, data):
                    self.send_response(status)
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

                def do_POST(self):
                    if not dispatch(self, scope=scope, authority=lambda: closing(sqlite3.connect(active_path)),
                                    witness=lambda: closing(sqlite3.connect(active_witness)),
                                    restore_permitted=lambda: guard, graph_reader=GraphFixture,
                                    publish_records=publisher, read_context=readbacks.__getitem__):
                        delegated.append(self.path)
                        self.reply(204, b'')

            with serve(Handler) as server:
                host = '127.0.0.1:' + str(server.server_port)
                def post(route, body=data, *, headers=None, raw=None):
                    raw = json.dumps(body).encode() if raw is None else raw
                    normal = {'Origin': 'http://' + host, 'Content-Type': 'application/json',
                              'Authorization': 'Bearer ' + token}
                    normal.update(headers or {})
                    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    try:
                        conn.request('POST', route, body=raw, headers=normal)
                        result = conn.getresponse()
                        return result.status, result.read()
                    finally:
                        conn.close()

                self.assertEqual(post(ADMIT)[0], 403)  # external restore lock
                guard = True
                for route in ('/api/v1/ingest/admit', '/api/v1/ingest/create', '/api/v1/ingest/persist',
                              '/api/v1/enterprise-clock/advance', '/api/v1/enterprise-clock/capture',
                              '/api/v1/enterprise-clock/capture-technical', '/api/v1/enterprise-clock/capture-scenarios',
                              '/api/v1/enterprise-parametric/configure', '/unknown', ADMIT + '?x=1'):
                    with self.subTest(route=route):
                        self.assertEqual(post(route)[0], 403)
                for headers in ({'Authorization': 'Bearer ' + '0' * 64}, {'Origin': 'http://invalid'},
                                {'Host': 'invalid'}, {'Content-Type': 'text/plain'}):
                    self.assertEqual(post(ADMIT, headers=headers)[0], 403)
                self.assertEqual(post(ADMIT, raw=b'{"generation":0,"generation":1,"rows":[]}')[0], 403)
                self.assertEqual(post(ADMIT, data | {'scope': list(scope)})[0], 403)
                self.assertEqual(post(ADMIT, data | {'generation': True})[0], 403)
                self.assertEqual(post(ADMIT, raw=b'x' * 4097)[0], 403)
                self.assertEqual(post('/api/v1/hitl/dynamic/request')[0], 204)
                self.assertEqual(delegated, ['/api/v1/hitl/dynamic/request'])
                self.assertEqual(calls, [])
                active_witness = path  # witness cannot be the authority itself
                self.assertEqual(post(ADMIT)[0], 403)
                active_witness = witness_path
                self.assertEqual(calls, [])
                if fail_publish:
                    self.assertEqual(post(ADMIT)[0], 403)
                    self.assertEqual(post(ADMIT)[0], 403)
                    query = {'generation': 0, 'episode': rows[0]['id'][:32], 'batch': digest(ingest(rows)['incidents'][0])}
                    self.assertEqual(post(RECEIPT, query)[0], 403)
                    with closing(sqlite3.connect(path)) as db, closing(sqlite3.connect(witness_path)) as witness:
                        self.assertEqual(db.execute('SELECT state FROM collector_fence').fetchone()[0], 'PENDING')
                        self.assertEqual(witness.execute('SELECT state FROM guard').fetchone()[0], 'BUSY')
                    self.assertEqual(len(calls), 1)
                    return
                status, raw = post(ADMIT)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw)['publication']['core']['run']['run_id'], 'RUN-0000000000000001')
                self.assertEqual(post(ADMIT)[0], 403)
                query = {'generation': 0, 'episode': rows[0]['id'][:32], 'batch': digest(ingest(rows)['incidents'][0])}
                status, raw = post(RECEIPT, query)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw)['state'], 'COMMITTED')
                with closing(sqlite3.connect(path)) as db, closing(sqlite3.connect(witness_path)) as witness:
                    self.assertEqual(witness.execute('SELECT state,digest FROM guard').fetchone(), ('READY', snapshot(db)))
                active_path = old_path
                self.assertEqual(post(ADMIT)[0], 403)
                self.assertEqual(post(RECEIPT, query)[0], 403)
                active_path = path
                guard = False
                self.assertEqual(post(RECEIPT, query)[0], 403)
                self.assertEqual(len(calls), 1)


class GammaGuardedIntegrationTests(unittest.TestCase):
    def test_explicit_server_wiring_and_legacy_denial(self):
        from threading import Thread
        from unittest.mock import patch
        from http_demo import server as gamma_server
        with tempfile.TemporaryDirectory() as tmp:
            authority_path = Path(tmp) / 'authority.db'
            witness_path = Path(tmp) / 'witness.db'
            scope = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-one')
            token = secrets.token_hex(32)
            with closing(sqlite3.connect(authority_path)) as db, closing(sqlite3.connect(witness_path)) as witness:
                initialize(db)
                provision(db, scope, token)
                provision_witness(db, witness)
            now = datetime.now(timezone.utc)
            windows = [{'at': (now - timedelta(seconds=age)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'median': value, 'samples': [value] * 5} for age, value in ((10, 10), (2, 100))]
            rows = batch(*windows)
            config = {'scope': scope,
                      'authority': lambda: closing(sqlite3.connect(authority_path)),
                      'witness': lambda: closing(sqlite3.connect(witness_path)),
                      'restore_permitted': lambda: True}
            core = (18101, 'x' * 32, 'RUN-CI-CONTEXT')
            context = (18102, 18103, 'NODE-CI-ROOT', 'INC-CI-CONTEXT')
            for invalid in ({**config, 'witness': None}, {**config, 'scope': ('synthetic-demo', 'NODE-CI-OTHER', 'COLLECTOR-one')}):
                with self.assertRaises(ValueError):
                    gamma_server(core_config=core, context_config=context, collector_guard=invalid)
            with self.assertRaises(ValueError):
                gamma_server(core_config=core, context_config=context, collector_guard=config, container_lab=True)
            with patch('http_demo.get', return_value={}) as graph_get, \
                    patch('http_demo.Graph', return_value=GraphFixture()), \
                    patch('http_demo.create_and_persist', side_effect=lambda r, p, t, e: response_for(r)['publication']) as publisher, \
                    patch('http_demo.dynamic_context', return_value=persisted_fixture(rows)) as reader:
                with gamma_server(core_config=core, context_config=context, collector_guard=config) as gamma:
                    thread = Thread(target=gamma.serve_forever, daemon=True)
                    thread.start()
                    try:
                        def call(route, data):
                            host = '127.0.0.1:' + str(gamma.server_port)
                            with closing(http.client.HTTPConnection('127.0.0.1', gamma.server_port, timeout=3)) as conn:
                                conn.request('POST', route, body=json.dumps(data).encode(), headers={
                                    'Origin': 'http://' + host, 'Content-Type': 'application/json',
                                    'Authorization': 'Bearer ' + token})
                                res = conn.getresponse()
                                return res.status, json.loads(res.read())
                        data = {'generation': 0, 'rows': rows}
                        for route in ('/api/v1/ingest/admit', '/api/v1/ingest/create', '/api/v1/ingest/persist',
                                      '/api/v1/enterprise-clock/advance', '/api/v1/enterprise-clock/capture'):
                            self.assertEqual(call(route, rows)[0], 403)
                        publisher.assert_not_called()
                        self.assertEqual(call('/api/v1/ingest', rows)[0], 200)
                        status, result = call(ADMIT, data)
                        self.assertEqual(status, 200)
                        run_id = result['publication']['core']['run']['run_id']
                        publisher.assert_called_once_with(rows, core[0], core[1], context[1])
                        reader.assert_called_once_with(core[0], core[1], run_id, context[0], context[1], context[2], include_signals=True)
                        graph_get.assert_called_once_with(context[0], '/api/twin/graph')
                        self.assertEqual(call(ADMIT, data)[0], 403)
                        query = {'generation': 0, 'episode': rows[0]['id'][:32], 'batch': digest(ingest(rows)['incidents'][0])}
                        self.assertEqual(call(RECEIPT, query), (200, {'state': 'COMMITTED', 'run_id': run_id, 'receipt_sha256': digest(result)}))
                        self.assertEqual(publisher.call_count, 1)
                        self.assertEqual(reader.call_count, 1)
                    finally:
                        gamma.shutdown()
                        thread.join()
            with gamma_server() as plain:
                self.assertIsNone(plain.collector_guard)



class LabCollectorConfigurationTests(unittest.TestCase):
    def test_explicit_provision_and_exclusive_lifetime(self):
        from collector_lab_config import provision_new, activation, maintenance_lock, paths, SCOPE
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises((OSError, ValueError)):
                with activation(root):
                    self.fail('missing files activated')
            self.assertEqual(list(root.iterdir()), [])
            provision_new(root)
            with self.assertRaises(ValueError):
                provision_new(root)
            control, authority_dir, witness_dir = paths(root)
            with activation(root) as config:
                self.assertEqual(config['scope'], SCOPE)
                self.assertTrue(config['restore_permitted']())
                with self.assertRaises(BlockingIOError):
                    with maintenance_lock(control):
                        self.fail('maintenance lock acquired twice')
                with config['authority']() as db, config['witness']() as guard:
                    self.assertEqual(guard.execute('SELECT state,digest FROM guard').fetchone(), ('READY', snapshot(db)))
                with self.assertRaises(BlockingIOError):
                    with activation(root):
                        self.fail('second server acquired lock')
            self.assertFalse(config['restore_permitted']())
            with self.assertRaises(ValueError):
                with config['authority']():
                    self.fail('expired activation opened authority')
            with activation(root) as restarted:
                self.assertTrue(restarted['restore_permitted']())
            self.assertEqual((control / 'collector.token').stat().st_mode & 0o077, 0)
            self.assertNotEqual(authority_dir, witness_dir)

    def test_missing_or_untrusted_database_never_recreated(self):
        from collector_lab_config import provision_new, activation, paths
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            provision_new(root)
            _, authority_dir, witness_dir = paths(root)
            authority = authority_dir / 'authority.db'
            witness = witness_dir / 'witness.db'
            with activation(root) as config:
                authority.rename(authority_dir / 'moved.db')
                self.assertFalse(config['restore_permitted']())
                with self.assertRaises(ValueError):
                    with config['authority']():
                        self.fail('missing authority recreated')
            self.assertFalse(authority.exists())
            (authority_dir / 'moved.db').rename(authority)
            witness.chmod(0o644)
            with self.assertRaises(ValueError):
                with activation(root):
                    self.fail('public witness accepted')
            witness.chmod(0o600)
            with closing(sqlite3.connect(witness)) as db:
                db.execute("UPDATE guard SET state='BUSY'")
                db.commit()
            with self.assertRaises(ValueError):
                with activation(root):
                    self.fail('BUSY witness unlocked')
            with closing(sqlite3.connect(witness)) as db:
                self.assertEqual(db.execute('SELECT state FROM guard').fetchone()[0], 'BUSY')



if __name__ == '__main__':
    unittest.main()
