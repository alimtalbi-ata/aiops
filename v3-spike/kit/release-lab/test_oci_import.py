"""Actual HTTP restore to an in-memory registry protocol fixture, not Docker."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit
from oci_import import restore, location_path
from oci_transport import digest
from test_oci_transport import TransportTests


class RestoreTests(unittest.TestCase):
    def setUp(self):
        source = TransportTests('test_roundtrip')
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.export = source.run_export()
        self.root = source.bundle
        self.expected = self.export['bom_sha256']
        self.items = {}
        self.tags = {}
        self.writes = 0
        self.corrupt = False
        self.foreign = False
        owner = self
        class Registry(BaseHTTPRequestHandler):
            def reply(self, status, value=None, location=None, body=b''):
                self.send_response(status)
                if value: self.send_header('Docker-Content-Digest', value)
                if location: self.send_header('Location', location)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if self.command != 'HEAD': self.wfile.write(body)
            def read_item(self):
                path = urlsplit(self.path).path
                key = owner.tags.get(path, path)
                if key not in owner.items: return self.reply(404)
                data = owner.items[key]
                self.reply(200, digest(data), body=(b'x'*len(data) if owner.corrupt and self.command=='GET' else data))
            do_HEAD = read_item
            do_GET = read_item
            def do_POST(self):
                owner.writes += 1
                self.reply(202, location=('http://example.invalid/' if owner.foreign else self.path+'fixture?_state=opaque'))
            def do_PUT(self):
                owner.writes += 1
                u = urlsplit(self.path); data = self.rfile.read(int(self.headers['Content-Length'])); d = digest(data)
                if '/uploads/' in u.path:
                    if parse_qs(u.query).get('digest') != [d]: return self.reply(400)
                    key = u.path.split('/uploads/')[0]+'/'+d
                else:
                    key = u.path.rsplit('/',1)[0]+'/'+d
                    owner.tags[u.path] = key
                owner.items[key] = data
                self.reply(201, d)
            def log_message(self, *_): pass
        server = ThreadingHTTPServer(('127.0.0.1',0), Registry)
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(thread.join,2); self.addCleanup(server.shutdown)
        self.port = server.server_port
    def run_restore(self): return restore(self.root, self.expected, self.port)
    def test_roundtrip(self):
        r=self.run_restore(); self.assertEqual(len(r['manifests']),10); self.assertEqual(len(self.items),30); self.assertEqual(self.writes,50)
    def test_wrong_expected(self):
        self.expected='sha256:'+'0'*64
        with self.assertRaises(ValueError): self.run_restore()
        self.assertEqual(self.writes,0)
    def test_existing(self):
        self.run_restore(); n=self.writes
        with self.assertRaises(ValueError): self.run_restore()
        self.assertEqual(self.writes,n)
    def test_corrupt_readback(self):
        self.corrupt=True
        with self.assertRaises(ValueError): self.run_restore()
        self.assertFalse(self.tags)
    def test_foreign_upload(self):
        self.foreign=True
        with self.assertRaises(ValueError): self.run_restore()
        self.assertEqual(self.writes,1); self.assertFalse(self.items)
    def test_location_paths(self):
        d='sha256:'+'a'*64; p='/v2/aiops-v3/core/blobs/uploads/abc'
        self.assertIn('digest=sha256%3A',location_path('http://127.0.0.1:15081'+p+'?_state=x','core',15081,d))
        for bad in ('http://127.0.0.1:15080'+p,'//example.invalid'+p,p+'?digest=bad',p.replace('/core/','/gamma/'),p+'#x',p+'/../evil'):
            with self.subTest(bad=bad), self.assertRaises(ValueError): location_path(bad,'core',15081,d)


if __name__ == '__main__': unittest.main()
