"""Ed25519 detached LAB distribution statement. Trust anchor supplied out of band."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

CLASSIFICATION = "V3_E17_LAB_DISTRIBUTION"
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
SOURCE = re.compile(r"[a-f0-9]{40}")
# Docker Engine may report a canonical UUID or a 64-character hex identity.
DAEMON = re.compile(r"[a-f0-9]{64}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}")
REGISTRY = re.compile(r"docker\.io/library/registry@sha256:[a-f0-9]{64}")
SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")
MAX_STATEMENT = 8192


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_regular(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= limit, "invalid input file")
        data = f.read(limit + 1)
        require(len(data) == info.st_size, "input changed while reading")
        return data


def statement(source, bom, archive, support, verifier, sbom, registry, producer_daemon):
    require(isinstance(source, str) and SOURCE.fullmatch(source), "invalid source")
    for value in (bom, archive, support, verifier, sbom):
        require(isinstance(value, str) and DIGEST.fullmatch(value), "invalid content digest")
    require(isinstance(registry, str) and REGISTRY.fullmatch(registry), "invalid registry bootstrap")
    require(isinstance(producer_daemon, str) and DAEMON.fullmatch(producer_daemon),
            "invalid producer daemon identity")
    return {"schema_version": 3, "classification": CLASSIFICATION,
            "source_sha": source, "bom_sha256": bom, "archive_sha256": archive,
            "support_manifest_sha256": support, "support_verifier_sha256": verifier,
            "sbom_index_sha256": sbom, "registry_reference": registry, "platform": "linux/amd64",
            "producer_daemon_id": producer_daemon, "production_authorized": False}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def create(path, source, bom, archive, support, verifier, sbom, registry, producer_daemon):
    data = canonical(statement(source, bom, archive, support, verifier, sbom, registry, producer_daemon))
    write_new(path, data)
    return sha(data)


def verify(path, signature, public_key, expected_key_sha, expected_source, expected_producer_daemon):
    require(isinstance(expected_key_sha, str) and DIGEST.fullmatch(expected_key_sha),
            "independently trusted key digest required")
    require(isinstance(expected_source, str) and SOURCE.fullmatch(expected_source),
            "expected source required")
    require(isinstance(expected_producer_daemon, str) and DAEMON.fullmatch(expected_producer_daemon),
            "expected producer daemon required")
    raw = read_regular(path, MAX_STATEMENT)
    sig = read_regular(signature, 64)
    key = read_regular(public_key, 44)
    require(len(sig) == 64 and len(key) == 44 and key.startswith(SPKI_PREFIX),
            "only Ed25519 detached signature and DER public key allowed")
    require(sha(key) == expected_key_sha, "untrusted public key")
    # OpenSSL sees immutable private temporary copies of the exact checked bytes.
    with tempfile.TemporaryDirectory(prefix="v3-signature-") as tmp:
        root = Path(tmp)
        for name, data in (("statement", raw), ("signature", sig), ("public.der", key)):
            write_new(root / name, data)
        result = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-pubin", "-keyform", "DER",
             "-inkey", str(root / "public.der"), "-rawin", "-in", str(root / "statement"),
             "-sigfile", str(root / "signature")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
        require(result.returncode == 0, "invalid signature")
    # Do not interpret unverified statement contents. Canonical reconstruction
    # rejects duplicate keys, extra fields, alternate encodings and scope changes.
    doc = json.loads(raw)
    expected = statement(expected_source, doc["bom_sha256"], doc["archive_sha256"],
                         doc["support_manifest_sha256"], doc["support_verifier_sha256"],
                         doc.get("sbom_index_sha256"), doc["registry_reference"], expected_producer_daemon)
    require(raw == canonical(expected), "noncanonical statement or wrong source/scope")
    return {"classification": CLASSIFICATION, "result": "PASS",
            "statement_sha256": sha(raw), "public_key_sha256": sha(key),
            "statement": expected, "production_authorized": False}


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "create" and len(args) == 9:
        print(create(Path(args[0]), *args[1:]))
    elif mode == "verify" and len(args) == 6:
        print(json.dumps(verify(*(Path(p) for p in args[:3]), *args[3:]), sort_keys=True))
    else:
        raise SystemExit("create NEW_MANIFEST SOURCE BOM ARCHIVE SUPPORT VERIFIER SBOM_INDEX REGISTRY PRODUCER_DAEMON | verify MANIFEST SIG PUBLIC_DER TRUSTED_KEY_SHA SOURCE EXPECTED_PRODUCER_DAEMON")
