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
