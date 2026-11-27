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


class EvidencePublicationTests(unittest.TestCase):
    def exercise(self, fault=None, *, status=200, count=2):
        import hashlib
        import json
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from ingestion_store import persist

        rows = [{'id': 'ci-'+str(i), 'source': 'monitor', 'kind': 'log',
                 'tenant': 'synthetic-demo', 'resource': 'NODE-CI-1',
                 'severity': 'critical', 'synthetic': True} for i in range(count)]
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def answer(self, data, code=200):
                raw = json.dumps(data).encode()
                self.send_response(code)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(('POST', self.path, self.headers.get('Authorization'), data))
                digest = hashlib.sha256(json.dumps(data['payload'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                self.server.receipt = {'evidence_id': 'EVD-'+str(len(calls)), 'payload_hash': digest}
                if fault == 'redirect':
                    self.send_response(302)
                    self.send_header('Location', '/redirected')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                elif fault == 'lost_ack':
                    self.close_connection = True
                elif fault == 'list':
                    self.answer([])
                elif fault == 'hash':
                    self.answer(dict(self.server.receipt, payload_hash='0'*64))
                elif fault == 'duplicate':
                    self.answer(dict(self.server.receipt, evidence_id='EVD-1'))
                elif fault in ('bad id', 'bad\nid', 'é', 'x'*129):
                    self.answer(dict(self.server.receipt, evidence_id=fault))
                else:
                    self.answer(self.server.receipt, status)
            def do_GET(self):
                calls.append(('GET', self.path, self.headers.get('Authorization'), None))
                self.answer(self.server.receipt)
            def log_message(self, *args):
                pass
        with HTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
            thread.start()
            try:
                if fault:
                    with self.assertRaises(ValueError):
                        persist(rows, server.server_port, 'RUN-CI-TEST')
                else:
                    result = persist(rows, server.server_port, 'RUN-CI-TEST')
                    self.assertEqual(len(result['stored_evidence']), count)
                    self.assertEqual([r['evidence_id'] for r in result['stored_evidence']], ['EVD-'+str(i+1) for i in range(count)])
            finally:
                server.shutdown()
                thread.join()
        self.assertTrue(all(c[:3] == ('POST', '/api/evidence', None) for c in calls))
        return calls

    def test_evidence_valid(self):
        for status in (200, 201):
            with self.subTest(status=status):
                calls = self.exercise(status=status)
                self.assertEqual(len(calls), 2)
                self.assertEqual([c[3]['external_id'] for c in calls], ['ci-0', 'ci-1'])

    def test_evidence_redirect_never_followed(self):
        self.assertEqual(len(self.exercise('redirect')), 1)

    def test_evidence_invalid_receipt_stops(self):
        for fault in ('list', 'hash', 'bad id', 'bad\nid', 'é', 'x'*129):
            with self.subTest(fault=fault):
                self.assertEqual(len(self.exercise(fault)), 1)

    def test_evidence_duplicate_reference_stops(self):
        self.assertEqual(len(self.exercise('duplicate', count=3)), 2)

    def test_evidence_ack_loss_stops(self):
        self.assertEqual(len(self.exercise('lost_ack')), 1)

    def test_core_token_remains_required(self):
        from bounded_http_transport import post_core_json
        for token in (None, '', 'short'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                post_core_json(12345, token, '/api/runs', {})
