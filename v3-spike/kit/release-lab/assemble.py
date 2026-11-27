"""Assemble the reusable disposable LAB kit from the actual verified OCI BOM."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

SERVICES=("postgres","core","twin","evidence","policy","temporal-postgres","temporal","worker","gamma")
HERE=Path(__file__).resolve().parent
KIT=HERE.parent
REPO=KIT.parents[1]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise ValueError(msg)
def main(bom_path,out):
    require(not out.exists() and out.parent.is_dir(),"new bundle directory required")
    bom=json.loads(bom_path.read_text())
    require(bom["classification"]=="DISPOSABLE_POC_IMAGE_BOM" and bom["production_authorized"] is False
            and re.fullmatch(r"[a-f0-9]{40}",bom["source_sha"]) and set(bom["images"])==set(SERVICES),"invalid lab BOM")
    compose=(HERE/"compose.template.yml").read_text()
    for service in SERVICES:
        row=bom["images"][service]
        require(row["os"]=="linux" and row["architecture"]=="amd64"
                and all(re.fullmatch(r"sha256:[a-f0-9]{64}",row[k]) for k in ("manifest_digest","config_digest","engine_image_id"))
                and row["reference"]=="127.0.0.1:15080/aiops-v3/"+service+"@"+row["manifest_digest"],"unverified image")
        marker="@IMAGE_"+service+"@"
        require(compose.count(marker)==1,"invalid template")
        compose=compose.replace(marker,row["reference"])
    require("@IMAGE_" not in compose and "build:" not in compose,"unresolved image")
    out.mkdir(mode=0o700)
    (out/"sql").mkdir()
    (out/"compose.yml").write_text(compose)
    (out/"image-bom.json").write_text(json.dumps(bom,sort_keys=True,indent=2)+"\n")
    for name in ("001_schema.sql","004_operational_model.sql","008_event_idempotency.sql"):
        shutil.copyfile(REPO/"db"/"migrations"/name,out/"sql"/name)
    for name in ("poc-execution-receipts.sql","poc-seed.sql"):
        shutil.copyfile(KIT/name,out/"sql"/name)
    # Public synthetic init SQL must remain readable after PostgreSQL drops privileges.
    for name in ("001_schema.sql","004_operational_model.sql","008_event_idempotency.sql","poc-execution-receipts.sql"):
        sql=out/"sql"/name
        sql.chmod(0o644)
        require(sql.stat().st_mode & 0o777 == 0o644,"invalid init SQL mode")
    for name in ("poc-temporal-boundary-smoke.py","poc-gamma-container-smoke.py","poc-image-bom.py"):
        shutil.copyfile(KIT/name,out/name)
    shutil.copyfile(HERE/"install-ci.py",out/"install-ci.py")
    shutil.copyfile(HERE/"README.md",out/"README.md")
    files={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
    manifest={"classification":"V3_DISPOSABLE_LAB_KIT","source_sha":bom["source_sha"],
              "production_authorized":False,"files":files}
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"result":"ASSEMBLED","files":len(files),"manifest_sha256":sha(out/"manifest.json"),
                      "production_authorized":False},sort_keys=True))

if __name__=="__main__":
    if len(sys.argv)!=3: raise SystemExit("assemble.py BOM NEW_BUNDLE")
    main(Path(sys.argv[1]),Path(sys.argv[2]))
