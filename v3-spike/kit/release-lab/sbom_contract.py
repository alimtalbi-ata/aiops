"""Bind SPDX package inventories to original LAB OCI manifests; not a CVE verdict."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from oci_transport import read_bom, require, digest, valid_digest

SYFT_VERSION = "1.38.0"
SYFT_ARCHIVE_SHA = "sha256:bc664debb00db1b9b4b9dae4ba1a29d99621e33b641b94b78b9048374b812a3d"
MAX_REPORT = 64 * 1024**2


def read_report(path):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_REPORT,
            "invalid report file")
    raw = path.read_bytes()
    require(len(raw) <= MAX_REPORT, "report too large")
    doc = json.loads(raw)
    require(doc.get("spdxVersion") in ("SPDX-2.2", "SPDX-2.3")
            and doc.get("SPDXID") == "SPDXRef-DOCUMENT"
            and doc.get("dataLicense") == "CC0-1.0", "not SPDX JSON")
    creators = doc.get("creationInfo", {}).get("creators", [])
    require(any(isinstance(c, str) and c.startswith("Tool: syft-" + SYFT_VERSION) for c in creators),
            "unexpected scanner version")
    packages = doc.get("packages")
    require(isinstance(packages, list) and 0 < len(packages) <= 100000, "empty or excessive inventory")
    ids = set()
    for package in packages:
        identifier = package.get("SPDXID")
        require(isinstance(identifier, str) and identifier.startswith("SPDXRef-") and identifier not in ids
                and isinstance(package.get("name"), str) and bool(package["name"]), "invalid package identity")
        ids.add(identifier)
    return raw, len(packages)


def image_identity(ref, row):
    info = json.loads(subprocess.check_output(["docker", "image", "inspect", ref], timeout=30))[0]
    require(info["Id"] == row["engine_image_id"] and info["Os"] == "linux"
            and info["Architecture"] == "amd64" and ref in info.get("RepoDigests", []),
            "local image identity differs from BOM")
    return info["Id"]


def scan(bom_path, out, syft):
    require(os.getenv("GITHUB_ACTIONS") == "true" and os.getuid() != 0
            and os.getenv("DOCKER_HOST") == f"unix:///run/user/{os.getuid()}/docker.sock",
            "disposable rootless CI only")
    info = json.loads(subprocess.check_output(["docker", "info", "--format", "{{json .}}"], timeout=30))
    require(any("name=rootless" in s for s in info["SecurityOptions"])
            and info["DockerRootDir"] == "/tmp/aiops-v3-rootless-ci/docker-data", "wrong daemon")
    require(syft.is_absolute() and syft.is_file() and not syft.is_symlink(), "scanner executable required")
    version = json.loads(subprocess.check_output([str(syft), "version", "-o", "json"], timeout=15))
    require(version.get("version") == SYFT_VERSION, "scanner version mismatch")
    raw_bom = bom_path.read_bytes()
    bom = read_bom(raw_bom)
    require(bom["source_sha"] == os.environ["GITHUB_SHA"], "wrong checkout BOM")
    out.mkdir(mode=0o700)
    rows = {}
    env = {**os.environ, "SYFT_CHECK_FOR_APP_UPDATE": "false"}
    for service, row in sorted(bom["images"].items()):
        ref = row["reference"]
        before = image_identity(ref, row)
        path = out / (service + ".spdx.json")
        subprocess.run([str(syft), "scan", "docker:" + ref, "-o", "spdx-json=" + str(path)],
                       env=env, check=True, timeout=300)
        require(image_identity(ref, row) == before, "image changed during scan")
        raw, count = read_report(path)
        rows[service] = {"reference": ref, "manifest_digest": row["manifest_digest"],
                         "config_digest": row["config_digest"], "engine_image_id": before,
                         "report_sha256": digest(raw), "packages": count}
    index = {"classification": "V3_E17_LAB_SBOM_INDEX", "result": "PASS",
             "source_sha": bom["source_sha"], "bom_sha256": digest(raw_bom),
             "scanner": {"name": "syft", "version": SYFT_VERSION, "archive_sha256": SYFT_ARCHIVE_SHA},
             "images": rows, "vulnerability_scan": "NOT_RUN", "production_authorized": False}
    (out / "index.json").write_text(json.dumps(index, sort_keys=True, indent=2) + "\n")
    return verify(bom_path, out)


def verify(bom_path, out):
    raw = bom_path.read_bytes()
    bom = read_bom(raw)
    require(out.is_dir() and not out.is_symlink(), "invalid report root")
    require({p.name for p in out.iterdir()} == {"index.json"} |
            {s + ".spdx.json" for s in bom["images"]}, "unexpected SBOM inventory")
    path = out / "index.json"
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_REPORT, "invalid index")
    index = json.loads(path.read_bytes())
    require(set(index) == {"classification", "result", "source_sha", "bom_sha256", "scanner", "images",
                           "vulnerability_scan", "production_authorized"}
            and index["classification"] == "V3_E17_LAB_SBOM_INDEX" and index["result"] == "PASS"
            and index["source_sha"] == bom["source_sha"] and index["bom_sha256"] == digest(raw)
            and index["production_authorized"] is False and index["vulnerability_scan"] == "NOT_RUN"
            and index["scanner"] == {"name": "syft", "version": SYFT_VERSION, "archive_sha256": SYFT_ARCHIVE_SHA}
            and set(index["images"]) == set(bom["images"]), "wrong SBOM index")
    for service, image in bom["images"].items():
        raw, count = read_report(out / (service + ".spdx.json"))
        expected = {k: image[k] for k in ("reference", "manifest_digest", "config_digest", "engine_image_id")}
        expected.update(report_sha256=digest(raw), packages=count)
        require(index["images"][service] == expected, "SBOM report or image binding mismatch")
    return index


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "scan" and len(args) == 3:
        result = scan(*(Path(p) for p in args))
    elif mode == "verify" and len(args) == 2:
        result = verify(*(Path(p) for p in args))
    else:
        raise SystemExit("scan BOM NEW_OUTPUT SYFT | verify BOM OUTPUT")
    print(json.dumps(result, sort_keys=True))
