import socketserver
import threading
import time
import unittest
from bounded_http_transport import get_json


class TransportTests(unittest.TestCase):
    def request(self, raw, *, slow=False, **kwargs):
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(4096)
                try:
                    if slow:
                        for byte in raw:
                            self.request.sendall(bytes([byte]))
                            time.sleep(.025)
                    else:
                        self.request.sendall(raw)
                except OSError:
                    pass
        with socketserver.TCPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            try:
                return get_json(server.server_address[1], 'x'*32, '/api/test', **kwargs)
            finally:
                thread.join()

    def reply(self, body, status=b'200 OK', **kwargs):
        return self.request(b'HTTP/1.1 '+status+b'\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body, **kwargs)

    def test_valid(self):
        self.assertEqual(self.reply(b'{"a":1}'), {'a':1})

    def test_invalid(self):
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'[]', b'\xff', b'{'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.reply(body)

    def test_status(self):
        with self.assertRaises(ValueError):
            self.reply(b'{}', status=b'302 Found')

    def test_limit(self):
        with self.assertRaises(ValueError):
            self.reply(b'{"a":123}', limit=5)

    def test_framing(self):
        for headers in (b"Content-Length: 9", b"Content-Length: 2\r\nContent-Length: 2", b"Transfer-Encoding: chunked\r\nContent-Length: 2"):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                self.request(b"HTTP/1.1 200 OK\r\n"+headers+b"\r\nConnection: close\r\n\r\n{}")

    def test_malformed_headers(self):
        for headers in (
            b"Content-Length: 2\r\nmalformed\r\nTransfer-Encoding: chunked",
            b"Content-Length: 2\r\nmalformed\r\nContent-Length: 99",
            b"Content-Length: 2\r\nInvalid Header: value\r\nContent-Length: 99",
            b" continuation\r\nContent-Length: 2",
        ):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                self.request(b"HTTP/1.1 200 OK\r\n"+headers+b"\r\nConnection: close\r\n\r\n{}")

    def test_close_delimited(self):
        self.assertEqual(self.request(b"HTTP/1.0 200 OK\r\nConnection: close\r\n\r\n{}"), {})

    def test_folded_length_rejected(self):
        with self.assertRaises(ValueError):
            self.request(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n 2\r\nConnection: close\r\n\r\n{}")

    def test_deadline(self):
        start = time.monotonic()
        with self.assertRaises(ValueError):
            self.reply(b'{}', slow=True, timeout=.15)
        self.assertLess(time.monotonic()-start, 1)

    def test_bad_parameters(self):
        for port, token, path in ((7770,'x'*32,'/api/test'), (12345,'short','/api/test'), (12345,'x'*32,'http://other/api/test')):
            with self.assertRaises(ValueError):
                get_json(port, token, path)


class CoreReadbackTests(unittest.TestCase):
    def read(self, payload):
        import json
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from core_read import read_run

        captured = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                captured.append((self.path, self.headers.get('Authorization')))
                body = json.dumps(payload).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        with HTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            try:
                return read_run(server.server_address[1], 'x'*32, 'RUN-CI-1')
            finally:
                thread.join()
                self.assertEqual(captured, [('/api/noc/runs/RUN-CI-1', 'Bearer '+'x'*32)])

    def payload(self):
        return {'data_classification': 'SYNTHETIC_CANONICAL_RUN',
                'live_remediation_authorized': False,
                'tenant_acl_qualified': False, 'runtime_authenticated': False,
                'run': {'run_id': 'RUN-CI-1', 'incident_id': 'INC-CI-1',
                        'mode': 'DEMO', 'status': 'OPEN'}}

    def test_core_preserves_deny(self):
        data = self.read(self.payload())
        self.assertEqual(data['policy'], 'DENY')
        self.assertIs(data['production_authorized'], False)
        self.assertIs(data['tenant_acl_qualified'], False)
        self.assertEqual(data['run'], self.payload()['run'])

    def test_core_rejects_flags(self):
        for key in ('live_remediation_authorized', 'tenant_acl_qualified', 'runtime_authenticated'):
            for value in (True, None, 0):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.read(dict(self.payload(), **{key: value}))

    def test_core_rejects_malformed_run(self):
        for run in (None, [], 'RUN-CI-1', {}, {'run_id': 'RUN-OTHER'}):
            with self.subTest(run=run), self.assertRaises(ValueError):
                self.read(dict(self.payload(), run=run))
        payload = self.payload()
        del payload['run']
        with self.assertRaises(ValueError):
            self.read(payload)

    def test_core_rejects_other_run(self):
        payload = self.payload()
        payload['run']['run_id'] = 'RUN-OTHER'
        with self.assertRaises(ValueError):
            self.read(payload)



class CorePublicationTests(unittest.TestCase):
    def exercise(self, *, fault=None, repetitions=1):
        import hashlib
        import json
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from core_ingest import create_run
        from ingestion_demo import ingest

        rows = [{'id': 'ci-1', 'source': 'monitor', 'kind': 'log',
                 'tenant': 'synthetic-demo', 'resource': 'NODE-CI-1',
                 'severity': 'critical', 'synthetic': True}]
        correlation = ingest(rows)
        digest = hashlib.sha256(json.dumps(correlation['incidents'][0], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        incident = 'INC-CI-INGEST-' + digest[:32]
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def answer(self, data, status=200):
                raw = json.dumps(data).encode()
                self.send_response(status)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append((self.path, self.headers.get('Authorization'), data))
                if self.path == '/api/incidents':
                    self.answer({'incident_id': incident, 'synthetic': True}, 503 if fault == 'incident' else 200)
                elif fault == 'lost_ack':
                    self.close_connection = True
                elif fault == 'missing_run':
                    self.answer({})
                else:
                    self.answer({'run_id': 'RUN-CI-1'})
            def do_GET(self):
                calls.append((self.path, self.headers.get('Authorization'), None))
                self.answer({'data_classification': 'SYNTHETIC_CANONICAL_RUN',
                             'live_remediation_authorized': False, 'tenant_acl_qualified': False,
                             'runtime_authenticated': False,
                             'run': {'run_id': 'RUN-CI-1', 'incident_id': incident,
                                     'mode': 'DEMO', 'status': 'OPEN'}})
            def log_message(self, *args):
                pass
        with HTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
            thread.start()
            try:
                for _ in range(repetitions):
                    if fault:
                        with self.assertRaises(ValueError):
                            create_run(rows, server.server_port, 'x'*32)
                    else:
                        result = create_run(rows, server.server_port, 'x'*32)
                        self.assertEqual(result['core']['policy'], 'DENY')
                        self.assertIs(result['production_authorized'], False)
                        self.assertEqual(result['correlation'], correlation)
            finally:
                server.shutdown()
                thread.join()
        self.assertTrue(all(call[1] == 'Bearer '+'x'*32 for call in calls))
        self.assertEqual(calls[0][2]['payload']['batch_sha256'], digest)
        return calls, digest

    def test_core_publication_stable_identity(self):
        calls, digest = self.exercise(repetitions=2)
        self.assertEqual([c[0] for c in calls], ['/api/incidents', '/api/runs', '/api/noc/runs/RUN-CI-1']*2)
        self.assertEqual(calls[:3], calls[3:])
        self.assertEqual(calls[1][2]['idempotency_key'], 'v3-ingest-'+digest)

    def test_incident_failure_stops(self):
        calls, _ = self.exercise(fault='incident')
        self.assertEqual([c[0] for c in calls], ['/api/incidents'])

    def test_uncertain_run_never_retried(self):
        for fault in ('lost_ack', 'missing_run'):
            with self.subTest(fault=fault):
                calls, _ = self.exercise(fault=fault)
                self.assertEqual([c[0] for c in calls], ['/api/incidents', '/api/runs'])

    def test_post_restricts_routes_and_body(self):
        from bounded_http_transport import post_core_json
        for path, body in (('/api/evidence', {}), ('/api/incidents', []),
                           ('/api/runs', {'x': float('nan')}), ('/api/runs', {'x': 'a'*65536})):
            with self.subTest(path=path), self.assertRaises(ValueError):
                post_core_json(12345, 'x'*32, path, body)
