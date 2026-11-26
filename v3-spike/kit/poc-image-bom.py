"""CI-only image BOM from a disposable loopback registry; no release publication."""
import json
import hashlib
import http.client
import os
from pathlib import Path
import re
import subprocess
import sys

SERVICES = ("postgres", "core", "twin", "evidence", "policy")
ORCHESTRATION_SERVICES = SERVICES + ("temporal-postgres", "temporal", "worker")
REGISTRY = "127.0.0.1:15080"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SHA = re.compile(r"[0-9a-f]{40}")

def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()

def image_info(ref):
    rows = json.loads(docker("image", "inspect", ref))
    if len(rows) != 1 or not DIGEST.fullmatch(rows[0]["Id"]):
        raise ValueError("invalid image identity")
    return rows[0]

def write_json(path, obj):
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")

def registry_manifest(service, expected_config):
    """Read the actual published single-platform manifest, not local RepoDigests."""
    if service not in ORCHESTRATION_SERVICES or not DIGEST.fullmatch(expected_config):
        raise ValueError("invalid registry manifest request")
    media=("application/vnd.oci.image.manifest.v1+json",
           "application/vnd.docker.distribution.manifest.v2+json")
    conn=http.client.HTTPConnection("127.0.0.1",15080,timeout=10)
    try:
        conn.request("GET","/v2/aiops-v3/"+service+"/manifests/ci",
                     headers={"Accept":", ".join(media)})
        response=conn.getresponse()
        raw=response.read(1048577)
        digest=response.getheader("Docker-Content-Digest")
        content_type=response.getheader("Content-Type","").split(";",1)[0].strip()
        if response.status!=200 or len(raw)>1048576 or content_type not in media:
            raise ValueError("single-platform registry manifest unavailable: "+service)
        if not isinstance(digest,str) or not DIGEST.fullmatch(digest) or digest!="sha256:"+hashlib.sha256(raw).hexdigest():
            raise ValueError("registry manifest digest mismatch: "+service)
        manifest=json.loads(raw)
        if manifest.get("schemaVersion")!=2 or manifest.get("mediaType",content_type)!=content_type or manifest.get("config",{}).get("digest")!=expected_config:
            raise ValueError("published manifest config differs from local image: "+service)
        return REGISTRY+"/aiops-v3/"+service+"@"+digest
    finally:
        conn.close()

def create(out, source_sha, services=SERVICES):
    if not SHA.fullmatch(source_sha):
        raise ValueError("invalid source SHA")
    images = {}
    for service in services:
        repo = REGISTRY + "/aiops-v3/" + service
        tag = repo + ":ci"
        info = image_info(tag)
        if services == ORCHESTRATION_SERVICES:
            platform=info["Os"]+"/"+info["Architecture"]
            if platform!="linux/amd64":
                raise ValueError("this disposable campaign qualifies linux/amd64 only")
            subprocess.run(["docker","push","--platform",platform,tag],check=True)
            ref=registry_manifest(service,info["Id"])
        else:
            subprocess.run(["docker", "push", tag], check=True)
            info = image_info(tag)
            refs = [r for r in info["RepoDigests"]
                    if r.startswith(repo + "@") and DIGEST.fullmatch(r.split("@", 1)[1])]
            if len(refs) != 1:
                raise ValueError("missing or ambiguous registry digest: " + service)
            ref = refs[0]
        subprocess.run(["docker", "pull", ref], check=True)
        pinned = image_info(ref)
        if pinned["Id"] != info["Id"]:
            raise ValueError("digest readback differs from build: " + service)
        images[service] = {"reference": ref, "manifest_digest": ref.split("@")[1],
                           "config_digest": pinned["Id"], "os": pinned["Os"],
                           "architecture": pinned["Architecture"]}
    bom = {"schema_version": 1, "classification": "DISPOSABLE_POC_IMAGE_BOM",
           "source_sha": source_sha, "production_authorized": False, "images": images}
    write_json(out / "image-bom.json", bom)
    # JSON is valid YAML; !reset is not required because up is always --no-build.
    write_json(out / "compose.pinned.json", {"services": {
        service: {"image": item["reference"]} for service, item in images.items()}})
    print("Image BOM generated for", source_sha)

def verify(out, container_ids, services=SERVICES):
    bom = json.loads((out / "image-bom.json").read_text())
    if set(bom["images"]) != set(services) or len(container_ids) != len(services):
        raise ValueError("missing service")
    if not SHA.fullmatch(bom["source_sha"]) or bom["production_authorized"] is not False:
        raise ValueError("invalid BOM scope")
    override = json.loads((out / "compose.pinned.json").read_text())
    receipts = {}
    for service, cid in zip(services, container_ids):
        if not re.fullmatch(r"[0-9a-f]{12,64}", cid):
            raise ValueError("invalid container identity")
        expected = bom["images"][service]
        repo = REGISTRY + "/aiops-v3/" + service
        if not DIGEST.fullmatch(expected["manifest_digest"]) or expected["reference"] != repo + "@" + expected["manifest_digest"]:
            raise ValueError("invalid digest reference")
        if override["services"][service]["image"] != expected["reference"]:
            raise ValueError("override differs from BOM")
        if not DIGEST.fullmatch(expected["config_digest"]):
            raise ValueError("invalid config digest")
        row, = json.loads(docker("inspect", "--type", "container", cid))
        if (row["Config"]["Labels"].get("com.docker.compose.service") != service
            or row["Config"]["Image"] != expected["reference"]
            or row["Image"] != expected["config_digest"]
            or row["State"]["Status"] != "running"
            or row["State"].get("Health", {}).get("Status") != "healthy"):
            raise ValueError("container not healthy or differs from BOM: " + service)
        receipts[service] = {"manifest_digest": expected["manifest_digest"],
                             "config_digest": row["Image"], "health": "healthy"}
    result = {"classification": "DISPOSABLE_POC_PINNED_START",
              "source_sha": bom["source_sha"], "production_authorized": False,
              "result": "PASS", "services": receipts}
    write_json(out / "pinned-start.json", result)
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("Disposable CI only")
    if len(sys.argv) == 4 and sys.argv[1] == "create":
        create(Path(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) == 8 and sys.argv[1] == "verify":
        verify(Path(sys.argv[2]), sys.argv[3:])
    elif len(sys.argv) == 4 and sys.argv[1] == "create-orchestration":
        create(Path(sys.argv[2]), sys.argv[3], ORCHESTRATION_SERVICES)
    elif len(sys.argv) == 3 + len(ORCHESTRATION_SERVICES) and sys.argv[1] == "verify-orchestration":
        verify(Path(sys.argv[2]), sys.argv[3:], ORCHESTRATION_SERVICES)
    else:
        raise SystemExit("usage: poc-image-bom.py create OUT SHA | verify OUT IDS... | create-orchestration OUT SHA | verify-orchestration OUT IDS...")
