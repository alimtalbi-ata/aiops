"""CI-only image BOM from a disposable loopback registry; no release publication."""
import json
import hashlib
import http.client
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

SERVICES = ("postgres", "core", "twin", "evidence", "policy")
ORCHESTRATION_SERVICES = SERVICES + ("temporal-postgres", "temporal", "worker")
GAMMA_SERVICES = ORCHESTRATION_SERVICES + ("gamma",)
E17_SERVICES = GAMMA_SERVICES + ("e17-target",)
E17_TARGET_ONLY = ("e17-target",)
PLATFORM_SERVICE_SETS = (ORCHESTRATION_SERVICES, GAMMA_SERVICES, E17_TARGET_ONLY)
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

def platform_config(ref, out):
    """Hash the exact linux/amd64 config exported by the local engine.

    Docker's image Id may identify an index/manifest, not its platform config.
    The archive is temporary and is never published as a CI artifact.
    """
    with tempfile.TemporaryFile(dir=out) as archive:
        subprocess.run(["docker","image","save","--platform","linux/amd64",ref],
                       stdout=archive,check=True)
        archive.seek(0)
        with tarfile.open(fileobj=archive,mode="r:") as saved:
            def read(name,limit):
                member=saved.getmember(name)
                if not member.isfile() or not 0<member.size<=limit:
                    raise ValueError("invalid bounded image metadata")
                stream=saved.extractfile(member)
                if stream is None:
                    raise ValueError("missing image metadata")
                return stream.read(limit+1)
            rows=json.loads(read("manifest.json",1048576))
            if not isinstance(rows,list) or len(rows)!=1:
                raise ValueError("expected exactly one exported platform image")
            name=rows[0]["Config"]
            if not re.fullmatch(r"(?:blobs/sha256/)?[a-f0-9]{64}(?:\\.json)?",name):
                raise ValueError("invalid config path")
            raw=read(name,4194304)
            digest="sha256:"+hashlib.sha256(raw).hexdigest()
            config=json.loads(raw)
            if config.get("os")!="linux" or config.get("architecture")!="amd64":
                raise ValueError("unexpected exported platform")
            if name.split("/")[-1].removesuffix(".json")!=digest.split(":")[1]:
                raise ValueError("exported config hash mismatch")
            return digest

def registry_manifest(service, expected_config):
    """Read the actual published single-platform manifest, not local RepoDigests."""
    if service not in E17_SERVICES or not DIGEST.fullmatch(expected_config):
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
            raise ValueError("published manifest config differs from local image: "+service+" expected="+expected_config+" actual="+str(manifest.get("config",{}).get("digest")))
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
        if services in PLATFORM_SERVICE_SETS:
            platform=info["Os"]+"/"+info["Architecture"]
            if platform!="linux/amd64":
                raise ValueError("this disposable campaign qualifies linux/amd64 only")
            subprocess.run(["docker","push","--platform",platform,tag],check=True)
            source_config=platform_config(tag,out)
            print("Source platform identity",service,"engine",info["Id"],"config",source_config,flush=True)
            ref=registry_manifest(service,source_config)
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
        if services in PLATFORM_SERVICE_SETS:
            pinned_config=platform_config(ref,out)
            if pinned_config!=source_config or pinned["Os"]!="linux" or pinned["Architecture"]!="amd64":
                raise ValueError("pinned platform config differs from source: "+service)
            images[service]={"reference":ref,"manifest_digest":ref.split("@")[1],
                             "config_digest":pinned_config,"engine_image_id":pinned["Id"],
                             "os":pinned["Os"],"architecture":pinned["Architecture"]}
            print("Registry readback identity",service,ref,pinned_config,pinned["Id"],flush=True)
        else:
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

def extend_e17(base_dir, target_dir, out, source_sha):
    """Combine the nine verified LAB images and the separately published E17 target.
    Re-read each pinned identity before emitting a new BOM; never label a product BOM.
    """
    if not SHA.fullmatch(source_sha) or out.exists():
        raise ValueError("invalid E17 BOM destination or source")
    def load(directory, services):
        bom = json.loads((directory / "image-bom.json").read_text())
        if (bom.get("schema_version") != 1
            or bom.get("classification") != "DISPOSABLE_POC_IMAGE_BOM"
            or bom.get("source_sha") != source_sha
            or bom.get("production_authorized") is not False
            or set(bom["images"]) != set(services)):
            raise ValueError("invalid E17 input BOM")
        for service, row in bom["images"].items():
            if (not DIGEST.fullmatch(row["manifest_digest"])
                or not DIGEST.fullmatch(row["config_digest"])
                or not DIGEST.fullmatch(row["engine_image_id"])
                or row["reference"] != REGISTRY+"/aiops-v3/"+service+"@"+row["manifest_digest"]
                or (row["os"], row["architecture"]) != ("linux","amd64")):
                raise ValueError("invalid pinned E17 image")
            info = image_info(row["reference"])
            if (info["Id"] != row["engine_image_id"]
                or (info["Os"], info["Architecture"]) != ("linux","amd64")
                or platform_config(row["reference"], directory) != row["config_digest"]
                or registry_manifest(service, row["config_digest"]) != row["reference"]):
                raise ValueError("E17 image identity changed")
        return bom["images"]
    images = {**load(base_dir,GAMMA_SERVICES), **load(target_dir,E17_TARGET_ONLY)}
    out.mkdir(mode=0o700)
    write_json(out/"image-bom.json", {"schema_version":1,
               "classification":"DISPOSABLE_POC_E17_IMAGE_BOM",
               "source_sha":source_sha,"production_authorized":False,"images":images})
    write_json(out/"compose.pinned.json", {"services":{
        service:{"image":row["reference"]} for service,row in images.items()}})
    print("E17 ten-image BOM generated for", source_sha)

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
        expected_engine=expected["config_digest"]
        if services in PLATFORM_SERVICE_SETS:
            expected_engine=expected["engine_image_id"]
            if not DIGEST.fullmatch(expected_engine) or image_info(expected["reference"])["Id"]!=expected_engine:
                raise ValueError("pinned engine identity changed")
            if platform_config(expected["reference"],out)!=expected["config_digest"]:
                raise ValueError("pinned platform configuration changed")
        row, = json.loads(docker("inspect", "--type", "container", cid))
        if (row["Config"]["Labels"].get("com.docker.compose.service") != service
            or row["Config"]["Image"] != expected["reference"]
            or row["Image"] != expected_engine
            or row["State"]["Status"] != "running"
            or row["State"].get("Health", {}).get("Status") != "healthy"):
            raise ValueError("container not healthy or differs from BOM: " + service)
        receipts[service] = {"manifest_digest": expected["manifest_digest"],
                             "config_digest": expected["config_digest"], "health": "healthy"}
        if services in PLATFORM_SERVICE_SETS:
            receipts[service]["engine_image_id"]=row["Image"]
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
    elif len(sys.argv)==4 and sys.argv[1]=="create-gamma":
        create(Path(sys.argv[2]),sys.argv[3],GAMMA_SERVICES)
    elif len(sys.argv)==4 and sys.argv[1]=="create-e17-target":
        create(Path(sys.argv[2]),sys.argv[3],E17_TARGET_ONLY)
    elif len(sys.argv)==6 and sys.argv[1]=="extend-e17":
        extend_e17(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]),sys.argv[5])
    elif len(sys.argv)==3+len(GAMMA_SERVICES) and sys.argv[1]=="verify-gamma":
        verify(Path(sys.argv[2]),sys.argv[3:],GAMMA_SERVICES)
    else:
        raise SystemExit("usage: poc-image-bom.py create/verify | create-orchestration/verify-orchestration | create-gamma/verify-gamma | create-e17-target | extend-e17")
