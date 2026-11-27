"""Install and qualify a fresh immutable LAB kit on the dedicated CI daemon."""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import secrets
import subprocess
import sys
import time

ROOT=Path("/tmp/aiops-v3-rootless-ci")
SERVICES=("postgres","core","twin","evidence","policy","temporal-postgres","temporal","worker","gamma")
VOLUMES=("postgres-data","temporal-data","gamma-audit")
FILES={"compose.yml","image-bom.json","install-ci.py","README.md","poc-temporal-boundary-smoke.py",
       "poc-gamma-container-smoke.py","poc-image-bom.py","sql/001_schema.sql","sql/004_operational_model.sql",
       "sql/008_event_idempotency.sql","sql/poc-execution-receipts.sql","sql/poc-seed.sql"}
def require(ok,msg):
    if not ok: raise ValueError(msg)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def failure_diagnostics(compose, env, bundle, state, slot, error):
    """Emit only allowlisted state and log categories, never raw logs or config."""
    def capture(*args):
        return subprocess.run([*compose,*args],env=env,cwd=bundle,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,timeout=10,check=True).stdout
    rows={}
    for service in SERVICES:
        row={"state":"UNAVAILABLE","exit_code":None,"health":"UNAVAILABLE","log_categories":[]}
        try:
            cid=capture("ps","-a","-q",service).decode().strip()
            if re.fullmatch(r"[a-f0-9]{12,64}",cid):
                raw=subprocess.check_output(["docker","inspect","--type","container","--format",
                    "{{json .State.Status}} {{.State.ExitCode}} {{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}}",
                    cid],env=env,stderr=subprocess.PIPE,timeout=10).decode().strip()
                match=re.fullmatch(r'"(created|running|paused|restarting|removing|exited|dead)" ([0-9]{1,3}) ("(?:starting|healthy|unhealthy)"|null)',raw)
                if match:
                    row.update(state=match[1],exit_code=int(match[2]),health=json.loads(match[3]))
                if service in ("postgres","temporal-postgres"):
                    # Bounded by line count; never emit the input, even on an unknown error.
                    logs=capture("logs","--no-color","--tail","40",service).lower()
                    for needle,label in ((b"permission denied","PERMISSION_DENIED"),
                                         (b"no space left","NO_SPACE"),(b"fatal:","POSTGRES_FATAL"),
                                         (b"error:","POSTGRES_ERROR")):
                        if needle in logs: row["log_categories"].append(label)
        except (OSError,ValueError,subprocess.SubprocessError):
            pass
        rows[service]=row
    report={"classification":"V3_LAB_INSTALL_FAILURE_DIAGNOSTICS","result":"FAIL","slot":int(slot),
            "error_type":type(error).__name__,"services":rows,"production_authorized":False}
    fd=os.open(state/"failure-diagnostics.json",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f: json.dump(report,f,sort_keys=True)
    print(json.dumps(report,sort_keys=True),flush=True)

def main(bundle,slot):
    require(os.getenv("GITHUB_ACTIONS")=="true" and os.getuid()!=0 and slot in ("1","2","3")
            and ROOT.resolve()==ROOT and ROOT.stat().st_uid==os.getuid() and not ROOT.stat().st_mode&0o077,
            "disposable rootless CI required")
    require(bundle==ROOT/("install-"+slot)/"bundle" and bundle.resolve()==bundle,"dedicated bundle required")
    env={k:v for k,v in os.environ.items() if not k.startswith(("COMPOSE_","V3_"))}
    def docker(*args):
        return subprocess.check_output(["docker",*args],env=env,text=True,timeout=60).strip()
    require("name=rootless" in docker("info","--format","{{json .SecurityOptions}}")
            and docker("info","--format","{{.DockerRootDir}}")==str(ROOT/"docker-data"),"wrong daemon")
    manifest=json.loads((bundle/"manifest.json").read_text())
    require(manifest["classification"]=="V3_DISPOSABLE_LAB_KIT" and manifest["production_authorized"] is False
            and set(manifest["files"])==FILES,"invalid manifest")
    require({p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()}==FILES|{"manifest.json"}
            and all(not p.is_symlink() for p in bundle.rglob("*")),"unexpected bundle content")
    for name,digest in manifest["files"].items():
        require(sha(bundle/name)==digest,"bundle file hash mismatch: "+name)
    bom=json.loads((bundle/"image-bom.json").read_text())
    require(bom["source_sha"]==manifest["source_sha"] and set(bom["images"])==set(SERVICES)
            and bom["production_authorized"] is False,"invalid BOM")
    project="v3-lab-install-"+slot
    for kind in ("container","volume","network"):
        require(not docker(kind,"ls","-aq" if kind=="container" else "-q","--filter","label=com.docker.compose.project="+project),"existing project resource")
    for name in VOLUMES:
        require(subprocess.run(["docker","volume","inspect",project+"_"+name],env=env,stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL).returncode!=0,"existing volume")
    state=bundle.parent
    secret=state/"poc.env"
    fd=os.open(secret,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        f.write("V3_DB_PASSWORD="+secrets.token_hex(24)+"\nV3_LAB_TOKEN="+secrets.token_hex(32)+"\n")
    compose=["docker","compose","--project-name",project,"--project-directory",str(bundle),
             "--env-file",str(secret),"-f",str(bundle/"compose.yml")]
    def run(*args,stdin=None,timeout=600):
        return subprocess.check_output([*compose,*args],input=stdin,env=env,cwd=bundle,timeout=timeout,stderr=subprocess.PIPE)
    started=time.monotonic()
    try:
        # Never log resolved configuration: it contains fresh local credentials.
        cfg=json.loads(run("config","--format","json"))
        require(set(cfg["services"])==set(SERVICES),"unexpected services")
        for service,row in cfg["services"].items():
            ref=bom["images"][service]["reference"]
            require(re.fullmatch(r"127\.0\.0\.1:15080/aiops-v3/"+service+r"@sha256:[a-f0-9]{64}",ref)
                    and row["image"]==ref and "build" not in row,"unverified compose image")
            require(not row.get("privileged") and not row.get("devices") and not row.get("network_mode"),"unsafe service")
            if service=="gamma":
                require(len(row["ports"])==1 and row["ports"][0]["host_ip"]=="127.0.0.1"
                        and str(row["ports"][0]["published"])=="18080","wrong GAMMA exposure")
            else:
                require(not row.get("ports"),"unexpected host port")
        run("up","-d","--no-build","--pull","always","--wait","--wait-timeout","300")
        ids={}
        config_reader=runpy.run_path(str(bundle/"poc-image-bom.py"))["platform_config"]
        for service in SERVICES:
            cid=run("ps","-q",service).decode().strip()
            require(re.fullmatch(r"[a-f0-9]{12,64}",cid),"missing service")
            row=json.loads(docker("inspect","--type","container",cid))[0]
            expected=bom["images"][service]
            require(row["Config"]["Image"]==expected["reference"] and row["Image"]==expected["engine_image_id"]
                    and row["Config"]["Labels"]["com.docker.compose.project"]==project
                    and row["State"]["Health"]["Status"]=="healthy","container identity/readiness mismatch")
            require(config_reader(expected["reference"],state)==expected["config_digest"],"platform config mismatch")
            full_id=row["Id"]
            require(re.fullmatch(r"[a-f0-9]{64}",full_id) and full_id.startswith(cid),"invalid full container identity")
            ids[service]=full_id
        for name in VOLUMES:
            row=json.loads(docker("volume","inspect",project+"_"+name))[0]
            require(row["Labels"]["com.docker.compose.project"]==project,"wrong volume owner")
        run("exec","-T","postgres","psql","-v","ON_ERROR_STOP=1","-U","aiops","-d","aiops",
            stdin=(bundle/"sql/poc-seed.sql").read_bytes())
        def counts():
            raw=run("exec","-T","postgres","psql","-v","ON_ERROR_STOP=1","-U","aiops","-d","aiops","-Atc",
                    "select (select count(*) from aiops.incidents),(select count(*) from aiops.runs),(select count(*) from aiops.evidence),(select count(*) from aiops.execution_receipts)")
            return tuple(map(int,raw.decode().strip().split("|")))
        before=counts()
        boundary=json.loads(run("exec","-T","worker","python","-",stdin=(bundle/"poc-temporal-boundary-smoke.py").read_bytes()))
        require(boundary["result"]=="PASS" and boundary["core_status"]=="BLOCKED" and boundary["business_stages_passed"]==0,"boundary failed")
        gamma=json.loads(subprocess.check_output([sys.executable,str(bundle/"poc-gamma-container-smoke.py"),"initial"],
                                                cwd=bundle,env=env,timeout=120))
        require(gamma["result"]=="PASS" and len(gamma["evidence"])==2 and len(gamma["decisions"])==2,"GAMMA failed")
        after=counts()
        require(tuple(a-b for a,b in zip(after,before))==(1,2,2,1),"unexpected DB delta")
        elapsed=round(time.monotonic()-started,3)
        require(elapsed<1800,"prepared installation exceeds 30 minutes")
        report={"classification":"V3_PREPARED_CLEAN_LAB_INSTALL","result":"PASS","slot":int(slot),"project":project,
                "elapsed_seconds":elapsed,"manifest_sha256":sha(bundle/"manifest.json"),"source_sha":bom["source_sha"],
                "container_ids":ids,"volumes":[project+"_"+name for name in VOLUMES],
                "boundary":boundary,"gamma":gamma,"db_delta":[1,2,2,1],"production_authorized":False}
        (state/"install-report.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
        print(json.dumps(report,sort_keys=True))
    except Exception as error:
        try:
            failure_diagnostics(compose,env,bundle,state,slot,error)
        except Exception:
            print("Failure diagnostics unavailable",file=sys.stderr)
        raise
    finally:
        # Only the prechecked, disposable project. Never delete arbitrary host data.
        try:
            run("down","--volumes","--remove-orphans",timeout=180)
        finally:
            secret.unlink()

if __name__=="__main__":
    if len(sys.argv)!=3: raise SystemExit("install-ci.py BUNDLE SLOT")
    main(Path(sys.argv[1]),sys.argv[2])
