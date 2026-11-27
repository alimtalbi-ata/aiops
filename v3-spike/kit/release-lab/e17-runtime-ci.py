"""Exercise the existing E17 target and Worker from digest-pinned images only.
Disposable GitHub rootless runner; not a product install or production action.
"""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path("/tmp/aiops-v3-rootless-ci")
PROJECT = "v3-e17-pinned-runtime-ci"
AUDIT = PROJECT + "-audit"
SERVICES = ("postgres","core","twin","evidence","policy","temporal-postgres","temporal","worker","gamma")
KIT = Path(__file__).resolve().parent.parent

def require(ok, message):
    if not ok:
        raise ValueError(message)

def main():
    require(os.getenv("GITHUB_ACTIONS")=="true" and os.getuid()!=0
            and ROOT.resolve()==ROOT and ROOT.stat().st_uid==os.getuid()
            and not ROOT.stat().st_mode&0o077, "isolated CI root required")
    require(os.environ.get("DOCKER_HOST")==f"unix:///run/user/{os.getuid()}/docker.sock",
            "dedicated rootless socket required")
    env={k:v for k,v in os.environ.items() if not k.startswith(("COMPOSE_","V3_"))}
    def call(args, data=None, timeout=600):
        result=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              env=env,cwd=ROOT,timeout=timeout)
        require(result.returncode==0,"command failed: "+" ".join(args[:2]))
        return result.stdout
    def docker(*args, **kw):
        return call(["docker",*args],**kw)
    require(b"name=rootless" in docker("info","--format","{{json .SecurityOptions}}")
            and docker("info","--format","{{.DockerRootDir}}").decode().strip()==str(ROOT/"docker-data"),
            "wrong Docker daemon")
    for kind in ("container","volume","network"):
        require(not docker(kind,"ls","-aq" if kind=="container" else "-q",
                           "--filter","label=com.docker.compose.project="+PROJECT).strip(),"existing project")
    require(AUDIT not in docker("volume","ls","--format","{{.Name}}").decode().splitlines(),
            "existing E17 audit")
    bom=json.loads((ROOT/"e17-bom/image-bom.json").read_text())
    base=json.loads((ROOT/"bom/image-bom.json").read_text())
    require(bom["classification"]=="DISPOSABLE_POC_E17_IMAGE_BOM"
            and bom["production_authorized"] is False
            and bom["source_sha"]==base["source_sha"]==os.environ["GITHUB_SHA"]
            and set(bom["images"])==set(SERVICES)|{"e17-target"},"wrong E17 BOM")
    for name in SERVICES:
        require(bom["images"][name]==base["images"][name],"base image changed")
    target=bom["images"]["e17-target"]
    require(re.fullmatch(r"127\.0\.0\.1:15080/aiops-v3/e17-target@sha256:[a-f0-9]{64}",target["reference"])
            and target["reference"].endswith("@"+target["manifest_digest"]),"invalid target reference")
    bundle=ROOT/"e17-runtime-bundle"
    call([sys.executable,str(KIT/"release-lab/assemble.py"),str(ROOT/"bom/image-bom.json"),str(bundle)])
    secret=ROOT/"e17-runtime.env"
    fd=os.open(secret,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        f.write("V3_DB_PASSWORD="+secrets.token_hex(24)+"\nV3_LAB_TOKEN="+secrets.token_hex(32)
                +"\nV3_E17_ACTIVITY_TOKEN="+secrets.token_hex(32)+"\n")
    overlay={"services":{
        "worker":{"environment":{"AIOPS_V3_E17_TARGET":"http://e17-target:816",
                                  "V3_E17_ACTIVITY_TOKEN":"${V3_E17_ACTIVITY_TOKEN:?required}"}},
        "e17-target":{"image":target["reference"],"profiles":["e17"],
             "user":"1000:1000","read_only":True,"tmpfs":["/tmp:mode=1777"],
             "environment":{"GITHUB_ACTIONS":"true","AIOPS_V3_E17_TARGET":"http://e17-target:816",
                 "AIOPS_INTERNAL_TOKEN":"${V3_LAB_TOKEN:?required}",
                 "V3_E17_ACTIVITY_TOKEN":"${V3_E17_ACTIVITY_TOKEN:?required}",
                 "PYTHONDONTWRITEBYTECODE":"1","NO_PROXY":"127.0.0.1,localhost"},
             "volumes":["e17-audit:/audit"],"networks":["backend"],"cap_drop":["ALL"],
             "security_opt":["no-new-privileges:true"]}},
        "volumes":{"e17-audit":{"external":True,"name":AUDIT}}}
    override=bundle/"e17.json"
    override.write_text(json.dumps(overlay))
    compose=["docker","compose","--project-name",PROJECT,"--project-directory",str(bundle),
             "--env-file",str(secret),"-f",str(bundle/"compose.yml"),"-f",str(override)]
    def run(*args, **kw):
        return call([*compose,*args],**kw)
    audit_created=False
    try:
        cfg=json.loads(run("--profile","e17","config","--format","json"))
        require(set(cfg["services"])==set(bom["images"]),"wrong topology")
        for name,row in cfg["services"].items():
            require(row["image"]==bom["images"][name]["reference"] and "build" not in row
                    and not row.get("privileged") and not row.get("devices")
                    and not row.get("network_mode"),"unsafe service or image mismatch")
            if name!="gamma":
                require(not row.get("ports"),"unexpected port")
        row=cfg["services"]["e17-target"]
        require(row["user"]=="1000:1000" and row["read_only"]
                and set(row["networks"])=={"backend"},"target confinement")
        require(len(row["volumes"])==1 and row["volumes"][0]["type"]=="volume"
                and row["volumes"][0]["source"]=="e17-audit"
                and row["volumes"][0]["target"]=="/audit","target mount not confined")
        require(cfg["networks"]["backend"]["internal"] is True,"backend not internal")
        docker("volume","create","--label","com.docker.compose.project="+PROJECT,AUDIT)
        audit_created=True
        docker("run","--rm","--network","none","--user","0:0","--cap-drop","ALL",
               "--cap-add","CHOWN","--security-opt","no-new-privileges",
               "--mount",f"type=volume,source={AUDIT},target=/audit","--entrypoint","python",
               target["reference"],"-c",
               'import os; assert not os.listdir("/audit"); os.chmod("/audit",0o700); os.chown("/audit",1000,1000)')
        run("up","-d","--no-build","--pull","always","--wait","--wait-timeout","300",*SERVICES)
        for name in SERVICES:
            cid=run("ps","-q",name).decode().strip()
            require(re.fullmatch(r"[a-f0-9]{12,64}",cid),"missing service")
            identity=json.loads(docker("inspect","--type","container",cid))[0]
            require(identity["Image"]==bom["images"][name]["engine_image_id"]
                    and identity["Config"]["Image"]==bom["images"][name]["reference"]
                    and identity["State"]["Health"]["Status"]=="healthy","service not pinned or healthy")
        run("exec","-T","postgres","psql","-v","ON_ERROR_STOP=1","-U","aiops","-d","aiops",
            data=(bundle/"sql/poc-seed.sql").read_bytes())
        boundary=json.loads(run("exec","-T","worker","python","-",
                                data=(bundle/"poc-temporal-boundary-smoke.py").read_bytes()))
        require(boundary["result"]=="PASS" and boundary["core_status"]=="BLOCKED"
                and boundary["business_stages_passed"]==0,"boundary gate failed")
        report=run("--profile","e17","run","--rm","--no-deps","--use-aliases","-T","e17-target")
        parsed=json.loads(report)
        require(parsed["result"]=="PASS" and parsed["activity_executor"]=="V3_PRODUCT_WORKER"
                and parsed["verification"]["status"]=="RECOVERED"
                and parsed["production_authorized"] is False,"actual E17 gate failed")
        (ROOT/"temporal-e17-product.json").write_bytes(report)
        readback=(KIT/"poc-temporal-e17-worker-readback.py").read_text()
        worker=run("exec","-T","worker","python","-c",readback,boundary["run_id"],data=report)
        (ROOT/"temporal-e17-product-worker.json").write_bytes(worker)
        run("restart","temporal")
        run("up","-d","--no-build","--no-recreate","--wait","--wait-timeout","300",*SERVICES)
        replay=run("exec","-T","worker","python","-c",readback,boundary["run_id"],data=report)
        require(json.loads(replay)==json.loads(worker),"history receipt changed")
        (ROOT/"temporal-e17-product-worker-replay.json").write_bytes(replay)
        recreated=run("--profile","e17","run","--rm","--no-deps","--use-aliases","-T","e17-target",
                      "audit-recreated",data=report)
        require(json.loads(recreated)["result"]=="PASS","recreated target gate failed")
        (ROOT/"temporal-e17-recreated-target.json").write_bytes(recreated)
        def snapshot():
            return [run("exec","-T","postgres","psql","-v","ON_ERROR_STOP=1","-U","aiops","-d","aiops","-Atc",
                        "select count(*), md5(coalesce(string_agg(to_jsonb(t)::text, '|' order by to_jsonb(t)::text), '')) from aiops."+table+" t")
                    for table in ("runs","run_events","evidence","gates","twin_nodes","twin_edges","command_receipts","execution_receipts")]
        before=snapshot()
        projection=call([sys.executable,str(KIT/"poc-e17-gamma-readback.py"),
                         "http://127.0.0.1:18080",str(ROOT),"product"])
        require(json.loads(projection)["result"]=="PASS" and before==snapshot(),"GAMMA readback mutated state")
        (ROOT/"temporal-e17-product-gamma.json").write_bytes(projection)
        print("E17 pinned target activity and GAMMA readback PASS; collector and full business stages NOT_RUN")
    finally:
        try:
            run("--profile","e17","down","--volumes","--remove-orphans",timeout=180)
        finally:
            try:
                if audit_created:
                    docker("volume","rm",AUDIT)
            finally:
                secret.unlink()

if __name__=="__main__":
    main()
