"""Disposable PostgreSQL logical backup/restore proof, synthetic data only.

Two independently created rootless containers. No product or historical databases,
no published ports, no reuse of existing volumes. Not a general backup command.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

ROOT = Path("/tmp/aiops-v3-rootless-ci")
MAX_DUMP = 32 * 1024**2
SQL = """
CREATE TABLE public.lab_evidence (
  tenant text NOT NULL, evidence_id text NOT NULL, payload jsonb NOT NULL,
  PRIMARY KEY (tenant,evidence_id)
);
CREATE TABLE public.lab_receipts (
  tenant text NOT NULL, receipt_id text NOT NULL, evidence_id text NOT NULL,
  decision text NOT NULL CHECK(decision='DENY'),
  PRIMARY KEY (tenant,receipt_id),
  FOREIGN KEY(tenant,evidence_id) REFERENCES public.lab_evidence(tenant,evidence_id)
);
INSERT INTO public.lab_evidence VALUES
 ('lab-a','E-1','{"measurement":121,"unit":"ms"}'),
 ('lab-b','E-1','{"measurement":11,"unit":"ms"}');
INSERT INTO public.lab_receipts VALUES ('lab-a','R-1','E-1','DENY'),('lab-b','R-1','E-1','DENY');
"""
SNAPSHOT = """
SELECT jsonb_build_object(
'evidence',(SELECT jsonb_agg(to_jsonb(t) ORDER BY tenant,evidence_id) FROM public.lab_evidence t),
'receipts',(SELECT jsonb_agg(to_jsonb(t) ORDER BY tenant,receipt_id) FROM public.lab_receipts t),
'constraints',(SELECT jsonb_agg(pg_get_constraintdef(oid) ORDER BY conname) FROM pg_constraint
 WHERE conrelid IN ('public.lab_evidence'::regclass,'public.lab_receipts'::regclass))
)::text;
"""


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def run(args, data=None, timeout=120, expect=0):
    r = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    require((r.returncode == 0) == (expect == 0), "command status mismatch: " + args[0] + " " + args[1])
    return r.stdout


def docker(*args, **kw):
    return run(["docker", *args], **kw)


def psql(container, sql, expect=0):
    return docker("exec", "-i", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                  "-U", "lab", "-d", "lab", "-At", data=sql.encode(), expect=expect)


def fresh_database(container):
    count = psql(container, "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','S','v','m','f');")
    require(count.strip() == b"0", "destination already contains application objects")


def restore(container, dump, expected):
    require(0 < len(dump) <= MAX_DUMP and sha(dump) == expected, "backup digest mismatch")
    fresh_database(container)
    docker("exec", "-i", container, "pg_restore", "--exit-on-error", "--single-transaction",
           "--no-owner", "--no-privileges", "-U", "lab", "-d", "lab", data=dump)


def snapshot(container):
    value = json.loads(psql(container, SNAPSHOT))
    require(len(value["evidence"]) == len(value["receipts"]) == 2, "wrong fixture cardinality")
    require({r["tenant"] for r in value["evidence"]} == {"lab-a","lab-b"}, "wrong tenant scope")
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def wait(container):
    for _ in range(60):
        r = subprocess.run(["docker","exec",container,"pg_isready","-U","lab","-d","lab"],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        if r.returncode == 0:
            try:
                # The image's initialization server uses only a Unix socket.
                # Wait until the final TCP server is ready.
                docker("exec",container,"pg_isready","-h","127.0.0.1","-U","lab","-d","lab")
                return
            except ValueError:
                pass
        time.sleep(1)
    raise ValueError("database readiness timeout")


def main(image, out):
    require(os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("RUNNER_ENVIRONMENT") == "github-hosted"
            and os.getuid() != 0 and os.getenv("DOCKER_HOST") == f"unix:///run/user/{os.getuid()}/docker.sock",
            "hosted disposable rootless CI required")
    require(ROOT.is_dir() and ROOT.resolve() == ROOT and ROOT.stat().st_uid == os.getuid()
            and not ROOT.stat().st_mode & 0o077 and out.parent == ROOT, "isolated root required")
    require(re.fullmatch(r"docker\.io/library/postgres@sha256:[a-f0-9]{64}", image), "pinned PostgreSQL required")
    info = json.loads(docker("info", "--format", "{{json .}}"))
    require(info["DockerRootDir"] == str(ROOT/"docker-data")
            and any("name=rootless" in s for s in info["SecurityOptions"]), "wrong daemon")
    require(not docker("container","ls","-aq").strip() and not docker("volume","ls","-q").strip(),
            "empty disposable daemon required")
    out.mkdir(mode=0o700)
    password = secrets.token_hex(24)
    envfile = ROOT/"pg-restore.env"
    fd = os.open(envfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        f.write("POSTGRES_USER=lab\nPOSTGRES_DB=lab\nPOSTGRES_PASSWORD="+password+"\n")
    created = []
    volumes = []
    try:
        for slot in ("source","destination"):
            name = "v3-pg-restore-"+slot
            vol = name+"-data"
            docker("volume","create","--label","v3.lab.restore=true",vol)
            volumes.append(vol)
            cid = docker("run","-d","--pull","never","--network","none","--name",name,
                         "--env-file",str(envfile),"--mount",f"type=volume,source={vol},target=/var/lib/postgresql/data",
                         image).decode().strip()
            require(re.fullmatch(r"[a-f0-9]{64}",cid),"invalid container identity")
            created.append(cid)
            wait(cid)
        src,dst=created
        require(src!=dst and volumes[0]!=volumes[1],"restore isolation failure")
        fresh_database(src); fresh_database(dst)
        psql(src,SQL)
        before=snapshot(src)
        dump=docker("exec",src,"pg_dump","-Fc","--no-owner","--no-privileges","-U","lab","-d","lab")
        require(0<len(dump)<=MAX_DUMP,"invalid logical backup size")
        expected=sha(dump)
        (out/"backup.dump").write_bytes(dump)
        # Negative control: bad digest cannot create any objects.
        try:
            restore(dst,dump,b"invalid".hex())
        except ValueError as exc:
            require(str(exc)=="backup digest mismatch","unexpected negative result")
        else:
            raise ValueError("tampered digest accepted")
        fresh_database(dst)
        # Stop original before restoring; no reads from source during restore.
        docker("stop",src)
        restore(dst,(out/"backup.dump").read_bytes(),expected)
        after=snapshot(dst)
        require(before==after,"restored rows or constraints changed")
        try:
            restore(dst,dump,expected)
        except ValueError as exc:
            require(str(exc)=="destination already contains application objects","unexpected overwrite result")
        else:
            raise ValueError("existing destination accepted")
        require(snapshot(dst)==after,"overwrite attempt changed data")
        psql(dst,"INSERT INTO public.lab_receipts VALUES ('lab-a','R-2','missing','DENY');",expect=1)
        psql(dst,"INSERT INTO public.lab_receipts VALUES ('lab-a','R-2','E-1','ALLOW');",expect=1)
        require(snapshot(dst)==after,"negative constraint test changed data")
        report={"classification":"V3_LAB_POSTGRES_LOGICAL_RESTORE","result":"PASS",
                "source_sha":os.environ["GITHUB_SHA"],"image":image,"backup_sha256":expected,
                "backup_bytes":len(dump),"snapshot_sha256":sha(before),"rows":4,
                "distinct_containers_and_volumes":True,"source_stopped_before_restore":True,
                "wrong_digest_refused":True,"overwrite_refused":True,"constraints_preserved":True,
                "product_database":False,"temporal_restore":"NOT_RUN","production_authorized":False}
        (out/"restore.json").write_text(json.dumps(report,sort_keys=True)+"\n")
        print(json.dumps(report,sort_keys=True))
    finally:
        try:
            for cid in reversed(created):
                docker("rm","-f",cid)
        finally:
            try:
                for vol in reversed(volumes):
                    docker("volume","rm",vol)
            finally:
                envfile.unlink()


if __name__=="__main__":
    image,out=sys.argv[1:]
    main(image,Path(out))
