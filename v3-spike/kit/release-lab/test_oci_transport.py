"""Loopback registry fixture with real HTTP; no Docker or production data."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from oci_transport import SERVICES, digest, export, verify


def encoded(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':')).encode()


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = {}
        self.requests = []
        config = encoded({'os': 'linux', 'architecture': 'amd64'})
        layer = b'synthetic-layer-bytes'
        cfg, ld = digest(config), digest(layer)
        self.store[cfg] = config
        self.store[ld] = layer
        manifest = encoded({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json', 'config': {'mediaType': 'application/vnd.oci.image.config.v1+json', 'digest': cfg, 'size': len(config)}, 'layers': [{'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip', 'digest': ld, 'size': len(layer)}]})
        self.md = digest(manifest)
        self.ld = ld
        self.store[self.md] = manifest
        self.bom = {'schema_version': 1, 'classification': 'DISPOSABLE_POC_E17_IMAGE_BOM', 'source_sha': 'a'*40, 'production_authorized': False, 'images': {s: {'reference': '127.0.0.1:15080/aiops-v3/'+s+'@'+self.md, 'manifest_digest': self.md, 'config_digest': cfg, 'engine_image_id': cfg, 'os': 'linux', 'architecture': 'amd64'} for s in SERVICES}}
        self.bom_path = self.root/'bom.json'
        self.bom_path.write_bytes(encoded(self.bom))
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                key = self.path.rsplit('/', 1)[-1]
                if key not in owner.store:
                    self.send_error(404); return
                raw = owner.store[key]
                self.send_response(200)
                self.send_header('Docker-Content-Digest', key)
                self.send_header('Content-Type', 'application/vnd.oci.image.manifest.v1+json' if '/manifests/' in self.path else 'application/octet-stream')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers(); self.wfile.write(raw)
            def log_message(self, *_): pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.bundle = self.root/'bundle'

    def run_export(self):
        return export(self.bom_path, self.bundle, self.server.server_port)

    def verify_bundle(self):
        return verify(self.bundle, digest(self.bom_path.read_bytes()))

    def test_roundtrip(self):
        r = self.run_export()
        self.assertEqual((r['images'], r['blobs'], len(self.requests)), (10, 3, 3))
        self.assertEqual(self.verify_bundle(), r)

    def test_corrupted_download(self):
        self.store[self.ld] = b'wrong-content-bytes!!'
        with self.assertRaises(ValueError): self.run_export()
        self.assertFalse((self.bundle/'image-bom.json').exists())

    def test_missing_blob(self):
        del self.store[self.ld]
        with self.assertRaises(ValueError): self.run_export()

    def test_corrupted_archive(self):
        self.run_export(); (self.bundle/'blobs'/self.ld[7:]).write_bytes(b'x'*len(self.store[self.ld]))
        with self.assertRaises(ValueError): self.verify_bundle()

    def test_extra_blob(self):
        self.run_export(); (self.bundle/'blobs'/'unknown').write_bytes(b'x')
        with self.assertRaises(ValueError): self.verify_bundle()

    def test_symlink_blob(self):
        self.run_export(); p = self.bundle/'blobs'/self.ld[7:]; target = self.root/'outside'; p.rename(target); p.symlink_to(target)
        with self.assertRaises(ValueError): self.verify_bundle()

    def test_wrong_bom_digest(self):
        self.run_export()
        with self.assertRaises(ValueError): verify(self.bundle, 'sha256:'+'0'*64)

    def test_external_registry(self):
        self.bom['images']['gamma']['reference'] = 'example.invalid/gamma@'+self.md
        self.bom_path.write_bytes(encoded(self.bom))
        with self.assertRaises(ValueError): self.run_export()
        self.assertFalse(self.requests)

    def test_existing_destination(self):
        self.bundle.mkdir()
        with self.assertRaises(FileExistsError): self.run_export()
        self.assertFalse(self.requests)

    def test_foreign_layer_url(self):
        m = json.loads(self.store[self.md]); m['layers'][0]['urls'] = ['https://example.invalid/layer']
        new = encoded(m); md = digest(new); self.store[md] = new
        for s, row in self.bom['images'].items():
            row['manifest_digest'] = md; row['reference'] = '127.0.0.1:15080/aiops-v3/'+s+'@'+md
        self.bom_path.write_bytes(encoded(self.bom))
        with self.assertRaises(ValueError): self.run_export()
        self.assertFalse(any(self.ld in p for p in self.requests))


if __name__ == '__main__': unittest.main()
