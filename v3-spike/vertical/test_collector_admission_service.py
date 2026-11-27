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
from collector_admission_service import publish, lookup
from collector_receipt import digest
from continuous_collector import batch, NoRedirect, SCOPE
from ingestion_demo import ingest
from test_collector_transition import response_for


class GraphFixture:
    def scope(self, root):
        assert root == 'NODE-CI-ROOT'

    def validate_signal(self, root, scope):
        self.scope(root)
        assert all(scope[k] == v for k, v in SCOPE.items())


class ServiceTests(unittest.TestCase):
    def test_http_claim_and_reconciliation(self):
        for fault in ('none', 'lost_ack', 'invalid_receipt', 'publisher_failure'):
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

                def publisher(records):
                    # Confirm the claim is committed before any external publication.
                    with closing(sqlite3.connect(path)) as db:
                        self.assertEqual(db.execute('SELECT state FROM collector_fence').fetchone()[0], 'PENDING')
                    publications.append(records)
                    if fault == 'publisher_failure':
                        raise OSError('synthetic failure')
                    result = response_for(records)['publication']
                    if fault == 'invalid_receipt':
                        result['stored_evidence'][0]['payload_hash'] = '0' * 64
                    return result

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_POST(self):
                        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                        try:
                            with closing(sqlite3.connect(path)) as db:
                                args = dict(scope=scope, authorization=self.headers.get('Authorization'), generation=body['generation'])
                                if self.path == '/publish':
                                    result = publish(db, **args, rows=body['rows'], graph=GraphFixture(), publish_records=publisher)
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
                    finally:
                        server.shutdown()
                        thread.join()


if __name__ == '__main__':
    unittest.main()
