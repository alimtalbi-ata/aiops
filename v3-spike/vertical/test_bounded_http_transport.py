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

    def test_deadline(self):
        start = time.monotonic()
        with self.assertRaises(ValueError):
            self.reply(b'{}', slow=True, timeout=.15)
        self.assertLess(time.monotonic()-start, 1)

    def test_bad_parameters(self):
        for port, token, path in ((7770,'x'*32,'/api/test'), (12345,'short','/api/test'), (12345,'x'*32,'http://other/api/test')):
            with self.assertRaises(ValueError):
                get_json(port, token, path)
