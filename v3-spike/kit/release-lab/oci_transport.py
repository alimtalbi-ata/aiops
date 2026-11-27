"""Export exact single-platform registry bytes; not an installer or a signature."""
import hashlib
import http.client
import json
from pathlib import Path
import re
import sys

SERVICES = set('postgres core twin evidence policy temporal-postgres temporal worker gamma e17-target'.split())
MANIFESTS = {'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'}
CONFIGS = {'application/vnd.oci.image.config.v1+json', 'application/vnd.docker.container.image.v1+json'}
LAYERS = {'application/vnd.oci.image.layer.v1.tar+gzip', 'application/vnd.docker.image.rootfs.diff.tar.gzip', 'application/vnd.oci.image.layer.v1.tar', 'application/vnd.oci.image.layer.v1.tar+zstd'}
MAX_BLOB = 2 * 1024**3
MAX_TOTAL = 12 * 1024**3


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r'sha256:[a-f0-9]{64}', value) is not None


def parse(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=unique)


def read_bom(raw):
    require(len(raw) <= 1024**2, 'oversize BOM')
    bom = parse(raw)
    require(bom['schema_version'] == 1 and bom['classification'] == 'DISPOSABLE_POC_E17_IMAGE_BOM' and bom['production_authorized'] is False, 'wrong LAB BOM')
    require(re.fullmatch(r'[a-f0-9]{40}', bom['source_sha']) and set(bom['images']) == SERVICES, 'wrong source or services')
    for service, row in bom['images'].items():
        require(all(valid_digest(row[k]) for k in ('manifest_digest', 'config_digest', 'engine_image_id')), 'invalid digest')
        require(row['reference'] == '127.0.0.1:15080/aiops-v3/' + service + '@' + row['manifest_digest'] and (row['os'], row['architecture']) == ('linux', 'amd64'), 'wrong registry or platform')
    return bom


def descriptor(row, media, limit):
    require(set(row) <= {'mediaType', 'digest', 'size', 'annotations'} and row['mediaType'] in media and valid_digest(row['digest']), 'unsupported descriptor')
    require(type(row['size']) is int and 0 < row['size'] <= limit, 'invalid descriptor size')
    return row['digest'], row['size']


def walk(bom, get):
    seen = {}
    def content(service, kind, value, size=None):
        if value in seen:
            require(size is None or seen[value] == size, 'inconsistent size')
        data, length = get(service, kind, value, size)
        require(0 < length <= MAX_BLOB and (size is None or length == size), 'blob size mismatch')
        require(value not in seen or seen[value] == length, 'inconsistent blob')
        seen[value] = length
        require(sum(seen.values()) <= MAX_TOTAL, 'archive too large')
        return data
    for service, row in sorted(bom['images'].items()):
        m = parse(content(service, 'manifests', row['manifest_digest']))
        require(m['schemaVersion'] == 2 and m['mediaType'] in MANIFESTS and set(m) <= {'schemaVersion', 'mediaType', 'config', 'layers', 'annotations'}, 'unsupported manifest')
        config, size = descriptor(m['config'], CONFIGS, 4 * 1024**2)
        require(config == row['config_digest'], 'config differs from BOM')
        cfg = parse(content(service, 'config', config, size))
        require((cfg['os'], cfg['architecture']) == ('linux', 'amd64'), 'unexpected config platform')
        require(isinstance(m['layers'], list) and 0 < len(m['layers']) <= 256, 'invalid layers')
        for layer in m['layers']:
            d, size = descriptor(layer, LAYERS, MAX_BLOB)
            content(service, 'blobs', d, size)
    return seen


def verify(root, expected_bom_sha):
    require(valid_digest(expected_bom_sha) and root.is_dir() and not root.is_symlink(), 'invalid root or expected BOM digest')
    require(set(p.name for p in root.iterdir()) == {'image-bom.json', 'blobs'}, 'unexpected root inventory')
    bom_path = root / 'image-bom.json'
    store = root / 'blobs'
    require(bom_path.is_file() and not bom_path.is_symlink() and store.is_dir() and not store.is_symlink(), 'unsafe archive path')
    require(bom_path.stat().st_size <= 1024**2, 'oversize BOM')
    raw = bom_path.read_bytes()
    require(digest(raw) == expected_bom_sha, 'BOM digest mismatch')
    bom = read_bom(raw)
    def get(service, kind, value, size):
        path = store / value[7:]
        require(path.is_file() and not path.is_symlink(), 'missing or unsafe blob')
        length = path.stat().st_size
        limit = 1024**2 if kind == 'manifests' else 4 * 1024**2 if kind == 'config' else MAX_BLOB
        require(0 < length <= limit and (size is None or length == size), 'blob size mismatch')
        with path.open('rb') as f:
            require('sha256:' + hashlib.file_digest(f, 'sha256').hexdigest() == value, 'blob digest mismatch')
        return (path.read_bytes() if kind != 'blobs' else None), length
    seen = walk(bom, get)
    require(set(p.name for p in store.iterdir()) == {d[7:] for d in seen}, 'unexpected blob inventory')
    return {'classification': 'V3_E17_CONTENT_EXPORT', 'result': 'PASS', 'source_sha': bom['source_sha'], 'bom_sha256': expected_bom_sha, 'images': len(SERVICES), 'blobs': len(seen), 'bytes': sum(seen.values()), 'production_authorized': False}


def export(bom_path, root, port=15080):
    require(bom_path.is_file() and not bom_path.is_symlink() and bom_path.stat().st_size <= 1024**2, 'invalid BOM path')
    raw = bom_path.read_bytes()
    bom = read_bom(raw)
    root.mkdir(mode=0o700)
    store = root / 'blobs'
    store.mkdir(mode=0o700)
    total = 0
    def get(service, kind, value, size):
        nonlocal total
        path = store / value[7:]
        if not path.exists():
            limit = 1024**2 if kind == 'manifests' else 4 * 1024**2 if kind == 'config' else size
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
            try:
                endpoint = 'manifests' if kind == 'manifests' else 'blobs'
                conn.request('GET', '/v2/aiops-v3/' + service + '/' + endpoint + '/' + value, headers={'Accept': ', '.join(sorted(MANIFESTS))} if kind == 'manifests' else {})
                resp = conn.getresponse()
                require(resp.status == 200 and resp.getheader('Docker-Content-Digest') == value, 'registry response mismatch')
                if kind == 'manifests':
                    require(resp.getheader('Content-Type', '').split(';')[0] in MANIFESTS, 'registry media type mismatch')
                h = hashlib.sha256()
                length = 0
                with path.open('xb') as f:
                    while chunk := resp.read(1024**2):
                        length += len(chunk)
                        require(length <= limit and total + length <= MAX_TOTAL, 'download exceeds limit')
                        h.update(chunk)
                        f.write(chunk)
                require('sha256:' + h.hexdigest() == value and (size is None or length == size), 'download digest or size mismatch')
                total += length
            finally:
                conn.close()
        return (path.read_bytes() if kind != 'blobs' else None), path.stat().st_size
    walk(bom, get)
    (root / 'image-bom.json').write_bytes(raw)
    return verify(root, digest(raw))


if __name__ == '__main__':
    mode, first, second = sys.argv[1:]
    if mode == 'export':
        result = export(Path(first), Path(second))
    elif mode == 'verify':
        result = verify(Path(first), second)
    else:
        raise SystemExit('export BOM NEW_ROOT | verify ROOT sha256:EXPECTED_BOM')
    print(json.dumps(result, sort_keys=True))
