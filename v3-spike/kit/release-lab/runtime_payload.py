"""Minimal E17 LAB runtime support tree; not a signed release or host installer."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys

KIT = 'v3-spike/kit/'
LAB = KIT + 'release-lab/'
FILES = frozenset([
    *('db/migrations/' + n for n in ('001_schema.sql', '004_operational_model.sql', '008_event_idempotency.sql')),
    *(KIT + n for n in ('poc-execution-receipts.sql', 'poc-seed.sql',
                        'poc-temporal-boundary-smoke.py', 'poc-gamma-container-smoke.py',
                        'poc-image-bom.py', 'poc-e17-gamma-readback.py',
                        'poc-temporal-e17-worker-readback.py')),
    *(LAB + n for n in ('assemble.py', 'compose.template.yml', 'install-ci.py', 'README.md',
                        'e17-runtime-ci.py', 'e17-history-evidence.py',
                        'oci_transport.py', 'oci_import.py', 'oci_envelope.py',
                        'runtime_payload.py', 'distribution_manifest.py', 'sbom_contract.py', 'e17_pg_restore.py')),
    'v3-spike/vertical/tests/gamma_oci_e17_readback.py',
])
MANIFEST = 'runtime-manifest.json'
MAX_FILE = 8 * 1024**2
MAX_TOTAL = 32 * 1024**2


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def read_regular(path, limit=MAX_FILE):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        info = os.fstat(f.fileno())
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= limit, 'invalid regular file')
        data = f.read(limit + 1)
        require(len(data) == info.st_size, 'file changed or exceeds limit')
        return data


def json_unique(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def safe_root(root):
    require(root.is_dir() and not root.is_symlink() and root.absolute() == root.resolve(),
            'real directory required')


def safe_path(root, name):
    path = root / name
    require(path.absolute() == path.resolve() and not path.is_symlink(), 'linked path refused')
    return path


def verify(root, expected_manifest, expected_source):
    require(re.fullmatch(r'sha256:[a-f0-9]{64}', expected_manifest) is not None
            and re.fullmatch(r'[a-f0-9]{40}', expected_source) is not None, 'expected identities required')
    safe_root(root)
    expected_dirs = {str(parent) for name in FILES for parent in Path(name).parents if str(parent) != '.'}
    files, dirs = set(), set()
    for path in root.rglob('*'):
        name = path.relative_to(root).as_posix()
        require(not path.is_symlink(), 'linked payload entry')
        if path.is_dir():
            dirs.add(name)
        elif path.is_file():
            files.add(name)
        else:
            raise ValueError('unsupported payload entry')
    require(files == FILES | {MANIFEST} and dirs == expected_dirs, 'unexpected payload inventory')
    raw = read_regular(root / MANIFEST)
    require(sha(raw) == expected_manifest, 'manifest digest mismatch')
    manifest = json_unique(raw)
    require(set(manifest) == {'classification', 'source_sha', 'production_authorized', 'files'}
            and manifest['classification'] == 'V3_E17_RUNTIME_SUPPORT'
            and manifest['source_sha'] == expected_source
            and manifest['production_authorized'] is False
            and set(manifest['files']) == FILES, 'invalid support manifest')
    total = 0
    for name in sorted(FILES):
        item = manifest['files'][name]
        data = read_regular(safe_path(root, name))
        require(set(item) == {'sha256', 'bytes'} and type(item['bytes']) is int
                and item['bytes'] == len(data) and item['sha256'] == sha(data), 'support file mismatch')
        total += len(data)
        require(total <= MAX_TOTAL, 'support payload exceeds limit')
    return {'classification': 'V3_E17_RUNTIME_SUPPORT', 'result': 'PASS',
            'source_sha': expected_source, 'manifest_sha256': expected_manifest,
            'files': len(FILES), 'bytes': total, 'production_authorized': False}


def stage(source, root, source_sha):
    safe_root(source)
    require(re.fullmatch(r'[a-f0-9]{40}', source_sha) is not None, 'source identity required')
    require(root.absolute() == root.resolve() and source.resolve() not in root.resolve().parents,
            'fresh destination outside source required')
    safe_root(root.parent)
    data = {}
    total = 0
    for name in sorted(FILES):
        data[name] = read_regular(safe_path(source, name))
        total += len(data[name])
        require(total <= MAX_TOTAL, 'support payload exceeds limit')
    root.mkdir(mode=0o700)
    try:
        for name, raw in data.items():
            dest = root / name
            dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(raw)
        manifest = {'classification': 'V3_E17_RUNTIME_SUPPORT', 'source_sha': source_sha,
                    'production_authorized': False,
                    'files': {name: {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in data.items()}}
        raw = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
        fd = os.open(root / MANIFEST, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
        return verify(root, sha(raw), source_sha)
    except BaseException:
        shutil.rmtree(root)
        raise


if __name__ == '__main__':
    mode, *args = sys.argv[1:]
    if mode == 'stage' and len(args) == 3:
        result = stage(Path(args[0]), Path(args[1]), args[2])
    elif mode == 'verify' and len(args) == 3:
        result = verify(Path(args[0]), args[1], args[2])
    else:
        raise SystemExit('stage SOURCE NEW_ROOT SOURCE_SHA | verify ROOT EXPECTED_MANIFEST SOURCE_SHA')
    print(json.dumps(result, sort_keys=True))
