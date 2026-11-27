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
from collector_http_boundary import dispatch, ADMIT, RECEIPT
from collector_receipt import digest
from continuous_collector import batch
from ingestion_demo import ingest
from test_collector_transition import response_for, persisted_fixture
from test_collector_admission_service import GraphFixture
from test_fenced_durable_collector import serve


class BoundaryTests(unittest.TestCase):
    def test_strict_fenced_ingress(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'authority.db'
            scope = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-one')
            token = secrets.token_hex(32)
            with closing(sqlite3.connect(path)) as db:
                initialize(db)
                provision(db, scope, token)
            now = datetime.now(timezone.utc)
            windows = [{'at': (now - timedelta(seconds=age)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'median': value, 'samples': [value] * 5} for age, value in ((10, 10), (2, 100))]
            rows = batch(*windows)
            data = {'generation': 0, 'rows': rows}
            calls, delegated = [], []
            guard = False
            readbacks = {}

            def publisher(records):
                calls.append(records)
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
                    if not dispatch(self, scope=scope, authority=lambda: closing(sqlite3.connect(path)),
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
                status, raw = post(ADMIT)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw)['publication']['core']['run']['run_id'], 'RUN-0000000000000001')
                self.assertEqual(post(ADMIT)[0], 403)
                query = {'generation': 0, 'episode': rows[0]['id'][:32], 'batch': digest(ingest(rows)['incidents'][0])}
                status, raw = post(RECEIPT, query)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw)['state'], 'COMMITTED')
                guard = False
                self.assertEqual(post(RECEIPT, query)[0], 403)
                self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
