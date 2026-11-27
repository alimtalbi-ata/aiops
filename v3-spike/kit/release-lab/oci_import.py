"""Rehydrate a disposable loopback registry from verified original OCI bytes."""
import hashlib
import http.client
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit
from oci_transport import MANIFESTS, read_bom, parse, require, verify


def location_path(location, service, port, digest):
    require(isinstance(location, str), 'missing upload location')
    u = urlsplit(location)
    require(not u.fragment and ((not u.scheme and not u.netloc) or
            (u.scheme == 'http' and u.netloc == f'127.0.0.1:{port}')), 'unsafe upload origin')
    require(re.fullmatch('/v2/aiops-v3/' + service + r'/blobs/uploads/[a-zA-Z0-9_-]+', u.path), 'unsafe upload path')
    params = parse_qsl(u.query, strict_parsing=True)
    require(len(params) <= 1 and all(k == '_state' and v for k, v in params), 'unsafe upload query')
    return u.path + '?' + urlencode(params + [('digest', digest)])


def restore(root, expected, port=15081):
    receipt = verify(root, expected)  # all bytes checked before network writes
    bom = read_bom((root / 'image-bom.json').read_bytes())
    store = root / 'blobs'
    def request(method, path, status, *, body=None, headers=None, check=None):
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=60)
        try:
            c.request(method, path, body=body, headers=headers or {})
            r = c.getresponse()
            require(r.status in status, f'unexpected registry status {method} {r.status}')
            result = check(r) if check else None
            return r.status, r.getheaders(), result
        finally:
            c.close()
    accept = {'Accept': ', '.join(sorted(MANIFESTS))}
    # Refuse pre-existing manifests (including the fixed import tag) before any writes.
    for service, row in sorted(bom['images'].items()):
        prefix = '/v2/aiops-v3/' + service
        for ref in (row['manifest_digest'], 'transport'):
            request('HEAD', prefix+'/manifests/'+ref, {404}, headers=accept)
    def check_bytes(r, path, value):
        require(r.getheader('Docker-Content-Digest') == value, 'readback digest header mismatch')
        h = hashlib.sha256(); size = 0
        expected_size = path.stat().st_size
        while chunk := r.read(1024**2):
            size += len(chunk)
            require(size <= expected_size, 'oversize readback')
            h.update(chunk)
        require(size == expected_size and 'sha256:'+h.hexdigest() == value, 'readback content mismatch')
    restored = {}
    for service, row in sorted(bom['images'].items()):
        prefix = '/v2/aiops-v3/' + service
        md = row['manifest_digest']; manifest_path = store/md[7:]
        manifest = parse(manifest_path.read_bytes())
        values = {d['digest'] for d in [manifest['config'], *manifest['layers']]}
        for value in sorted(values):
            path = store/value[7:]
            endpoint = prefix+'/blobs/'+value
            status, _, _ = request('HEAD', endpoint, {200,404})
            if status == 404:
                _, headers, _ = request('POST', prefix+'/blobs/uploads/', {202}, body=b'', headers={'Content-Length':'0'})
                locations = [v for k,v in headers if k.lower() == 'location']
                require(len(locations) == 1, 'ambiguous upload location')
                upload = location_path(locations[0], service, port, value)
                with path.open('rb') as f:
                    request('PUT', upload, {201}, body=f, headers={'Content-Type':'application/octet-stream','Content-Length':str(path.stat().st_size)}, check=lambda r: require(r.getheader('Docker-Content-Digest') == value, 'upload digest mismatch'))
            request('GET', endpoint, {200}, check=lambda r: check_bytes(r, path, value))
        request('PUT', prefix+'/manifests/transport', {201}, body=manifest_path.read_bytes(), headers={'Content-Type':manifest['mediaType']}, check=lambda r: require(r.getheader('Docker-Content-Digest') == md, 'manifest digest changed'))
        request('GET', prefix+'/manifests/'+md, {200}, headers=accept, check=lambda r: check_bytes(r, manifest_path, md))
        restored[service] = md
    return {**receipt, 'classification':'V3_E17_CONTENT_RESTORE', 'registry':'127.0.0.1:'+str(port), 'manifests':restored}


if __name__ == '__main__':
    import os
    if os.getenv('GITHUB_ACTIONS') != 'true' or os.getuid() == 0:
        raise SystemExit('disposable rootless CI only')
    root, expected = sys.argv[1:]
    print(json.dumps(restore(Path(root), expected), sort_keys=True))
