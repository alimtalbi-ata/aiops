"""HTTP loopback fixture, real SQLite/admission logic, mocked Twin/Core/Evidence."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler, Request

from collector_admission_fence import initialize, provision
from collector_admission_service import publish, lookup, publish_guarded, lookup_guarded
from authority_restore_guard_candidate import provision_witness, snapshot, RestoreBlocked
from collector_admission_fence import FenceRejected
from collector_receipt import digest
from continuous_collector import batch, NoRedirect, SCOPE
from ingestion_demo import ingest
from test_collector_transition import response_for, persisted_fixture


class GraphFixture:
    def scope(self, root):
        assert root == 'NODE-CI-ROOT'

    def validate_signal(self, root, scope):
        self.scope(root)
        assert all(scope[k] == v for k, v in SCOPE.items())


class ServiceTests(unittest.TestCase):
    def test_http_claim_and_reconciliation(self):
        for fault in ('none', 'lost_ack', 'invalid_receipt', 'publisher_failure', 'swap_ids',
                      'foreign_ids', 'rehashed_run', 'reader_failure'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'authority.db'
                scope = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-one')
                auth = 'Bearer ' + secrets.token_hex(32)
                with closing(sqlite3.connect(path)) as db:
                    initialize(db)
                    provision(db, scope, auth[7:])
                now = datetime.now(timezone.utc)
                windows = [{'at': (now - timedelta(seconds=age)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'median': value, 'samples': [value] * 5} for age, value in ((10, 10), (2, 100))]
                rows = batch(*windows)
                episode = rows[0]['id'][:32]
                batch_hash = digest(ingest(rows)['incidents'][0])
                publications = []
                readbacks = {}
                reads = []

                def publisher(records):
                    # Confirm the claim is committed before any external publication.
                    with closing(sqlite3.connect(path)) as db:
                        self.assertEqual(db.execute('SELECT state FROM collector_fence').fetchone()[0], 'PENDING')
                    publications.append(records)
                    if fault == 'publisher_failure':
                        raise OSError('synthetic failure')
                    result = response_for(records)['publication']
                    core, context = persisted_fixture(records)
                    readbacks[core['run']['run_id']] = (core, context)
                    if fault == 'invalid_receipt':
                        result['stored_evidence'][0]['payload_hash'] = '0' * 64
                    elif fault == 'swap_ids':
                        refs = result['stored_evidence']
                        refs[0]['evidence_id'], refs[1]['evidence_id'] = refs[1]['evidence_id'], refs[0]['evidence_id']
                    elif fault == 'foreign_ids':
                        for i, ref in enumerate(result['stored_evidence']):
                            ref['evidence_id'] = 'FOREIGN-' + str(i)
                    elif fault == 'rehashed_run':
                        run = result['core']['run']
                        run['run_id'] = 'RUN-0000000000000002'
                        incident = result['correlation']['incidents'][0]
                        for ref, signal in zip(result['stored_evidence'], incident['evidence']):
                            ref['payload_hash'] = digest({'run_id': run['run_id'], 'incident_id': run['incident_id'],
                                'signal': signal, 'correlation_id': incident['id'], 'resource': incident['resource']})
                    return result

                def read_context(rid):
                    reads.append(rid)
                    with closing(sqlite3.connect(path)) as db:
                        self.assertEqual(db.execute('SELECT state FROM collector_fence').fetchone()[0], 'PENDING')
                    if fault == 'reader_failure':
                        raise OSError('synthetic readback unavailable')
                    return readbacks[rid]

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_POST(self):
                        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                        try:
                            with closing(sqlite3.connect(path)) as db:
                                args = dict(scope=scope, authorization=self.headers.get('Authorization'), generation=body['generation'])
                                if self.path == '/publish':
                                    result = publish(db, **args, rows=body['rows'], graph=GraphFixture(), publish_records=publisher, read_context=read_context)
                                    if fault == 'lost_ack':
                                        self.close_connection = True
                                        return
                                else:
                                    result = lookup(db, **args, episode=body['episode'], batch=body['batch'])
                            status = 200
                        except Exception:
                            status, result = 409, {'state': 'UNKNOWN_BLOCKED'}
                        self.send_response(status)
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())

                with HTTPServer(('127.0.0.1', 0), Handler) as server:
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        origin = 'http://127.0.0.1:' + str(server.server_port)
                        opener = build_opener(ProxyHandler({}), NoRedirect())
                        def call(route, payload, token=auth):
                            req = Request(origin + route, data=json.dumps(payload).encode(), headers={'Authorization': token})
                            with opener.open(req, timeout=3) as res:
                                return json.load(res)
                        data = {'generation': 0, 'rows': rows}
                        with self.assertRaises(HTTPError):
                            call('/publish', data, 'Bearer ' + '0' * 64)
                        with self.assertRaises(HTTPError):
                            call('/publish', data | {'generation': 1})
                        foreign = [dict(row, resource='NODE-CI-OTHER') for row in rows]
                        with self.assertRaises(HTTPError):
                            call('/publish', data | {'rows': foreign})
                        self.assertEqual(publications, [])
                        if fault == 'none':
                            result = call('/publish', data)
                            self.assertEqual(result['publication']['core']['run']['run_id'], 'RUN-0000000000000001')
                        else:
                            with self.assertRaises((HTTPError, OSError)):
                                call('/publish', data)
                        for retry in (rows, batch(*windows)):
                            with self.assertRaises(HTTPError):
                                call('/publish', data | {'rows': retry})
                        query = {'generation': 0, 'episode': episode, 'batch': batch_hash}
                        recovered = call('/lookup', query)
                        if fault in ('none', 'lost_ack'):
                            self.assertEqual(recovered['state'], 'COMMITTED')
                            self.assertEqual(recovered['run_id'], 'RUN-0000000000000001')
                            if fault == 'none':
                                self.assertEqual(recovered['receipt_sha256'], digest(result))
                        else:
                            self.assertEqual(recovered, {'state': 'UNKNOWN_BLOCKED'})
                        with self.assertRaises(HTTPError):
                            call('/lookup', query | {'batch': '0' * 64})
                        self.assertEqual(len(publications), 1)
                        self.assertEqual(len(reads), 0 if fault in ('publisher_failure', 'invalid_receipt') else 1)
                        with closing(sqlite3.connect(path)) as db:
                            self.assertEqual(db.execute('SELECT state FROM collector_fence').fetchone()[0],
                                             'COMMITTED' if fault in ('none', 'lost_ack') else 'PENDING')
                    finally:
                        server.shutdown()
                        thread.join()


class GuardedServiceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.connect('authority.db')
        self.witness = self.connect('witness.db')
        self.scope = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-one')
        self.auth = 'Bearer ' + secrets.token_hex(32)
        initialize(self.db)
        provision(self.db, self.scope, self.auth[7:])
        provision_witness(self.db, self.witness)
        now = datetime.now(timezone.utc)
        self.rows = batch(*[{'at': (now - timedelta(seconds=age)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                             'median': value, 'samples': [value] * 5}
                            for age, value in ((10, 10), (2, 100))])
        self.episode = self.rows[0]['id'][:32]
        self.batch = digest(ingest(self.rows)['incidents'][0])
        self.calls = []
        self.reads = []

    def connect(self, name):
        db = sqlite3.connect(self.root / name)
        self.addCleanup(db.close)
        return db

    def state(self):
        return (self.db.execute('SELECT state FROM collector_fence').fetchone()[0],
                self.witness.execute('SELECT state FROM guard').fetchone()[0])

    def publisher(self, rows):
        self.assertEqual(self.state(), ('PENDING', 'BUSY'))
        self.calls.append(rows)
        return response_for(rows)['publication']

    def reader(self, run_id):
        self.assertEqual(self.state(), ('PENDING', 'BUSY'))
        self.reads.append(run_id)
        return persisted_fixture(self.rows)

    def publish(self, **overrides):
        args = dict(scope=self.scope, authorization=self.auth, generation=0, rows=self.rows,
                    graph=GraphFixture(), publish_records=self.publisher, read_context=self.reader)
        args.update(overrides)
        return publish_guarded(self.db, self.witness, **args)

    def lookup(self, db=None, **overrides):
        args = dict(scope=self.scope, authorization=self.auth, generation=0,
                    episode=self.episode, batch=self.batch)
        args.update(overrides)
        return lookup_guarded(db if db is not None else self.db, self.witness, **args)

    def test_guarded_nominal_and_replay(self):
        result = self.publish()
        self.assertEqual(self.state(), ('COMMITTED', 'READY'))
        self.assertEqual(self.lookup(), {'state': 'COMMITTED',
                         'run_id': result['publication']['core']['run']['run_id'],
                         'receipt_sha256': digest(result)})
        self.assertEqual(self.witness.execute('SELECT digest FROM guard').fetchone()[0], snapshot(self.db))
        with self.assertRaises(FenceRejected):
            self.publish()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.reads), 1)
        self.assertEqual(self.state(), ('COMMITTED', 'READY'))

    def test_guarded_prevalidation_does_not_poison_witness(self):
        before = snapshot(self.db)
        for overrides in ({'authorization': 'Bearer ' + '0' * 64}, {'generation': 1},
                          {'rows': self.rows[:2]}, {'rows': [dict(r, resource='NODE-CI-OTHER') for r in self.rows]}):
            with self.subTest(overrides=list(overrides)):
                with self.assertRaises(FenceRejected):
                    self.publish(**overrides)
                self.assertEqual(self.state(), ('ARMED', 'READY'))
                self.assertEqual(snapshot(self.db), before)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [])

    def test_guarded_publication_failure_latches(self):
        def fail(rows):
            self.publisher(rows)
            raise OSError('synthetic publication uncertainty')
        with self.assertRaises(OSError):
            self.publish(publish_records=fail)
        self.assertEqual(self.state(), ('PENDING', 'BUSY'))
        with self.assertRaises(RestoreBlocked):
            self.publish()
        with self.assertRaises(RestoreBlocked):
            self.lookup()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.reads, [])

    def test_guarded_readback_failure_latches(self):
        def fail(run_id):
            self.reader(run_id)
            raise OSError('synthetic readback uncertainty')
        with self.assertRaises(OSError):
            self.publish(read_context=fail)
        self.assertEqual(self.state(), ('PENDING', 'BUSY'))
        with self.assertRaises(RestoreBlocked):
            self.lookup()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.reads), 1)

    def test_guarded_old_authority_refused(self):
        old = self.connect('old.db')
        self.db.backup(old)
        self.publish()
        with self.assertRaises(RestoreBlocked):
            self.lookup(old)
        with self.assertRaises(RestoreBlocked):
            publish_guarded(old, self.witness, scope=self.scope, authorization=self.auth,
                            generation=0, rows=self.rows, graph=GraphFixture(),
                            publish_records=self.publisher, read_context=self.reader)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.state(), ('COMMITTED', 'READY'))


if __name__ == '__main__':
    unittest.main()
