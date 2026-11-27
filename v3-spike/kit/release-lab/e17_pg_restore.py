"""Check actual E17 LAB application schema restore before disposable runtime teardown.

Called only from guarded rootless E17 harness. Not a general backup utility.
Temporal and collector authority are not restored by this check.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time

TABLES = {
    "runs", "run_events", "evidence", "gates", "twin_nodes", "twin_edges",
    "scenarios", "command_receipts", "twin_facts", "incidents", "observations",
    "changes", "impact_assessments", "scenario_steps", "run_stage_state",
    "api_audit", "execution_receipts",
}
WRITERS = ("gamma", "worker", "core", "twin", "evidence", "policy")
MAX_BYTES = 32 * 1024**2


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def snapshot(query):
    tables = set(query("SELECT tablename FROM pg_tables WHERE schemaname='aiops' ORDER BY tablename;").decode().splitlines())
    require(tables == TABLES, "unexpected LAB application tables")
    result = {}
    total = 0
    for table in sorted(tables):
        require(re.fullmatch(r"[a-z_]+", table), "invalid table identifier")
        raw = query('SELECT to_jsonb(t)::text FROM aiops.'+table+' t ORDER BY to_jsonb(t)::text COLLATE "C";')
        count = int(query("SELECT count(*) FROM aiops."+table+";"))
        total += len(raw)
        require(total <= MAX_BYTES and len(raw.splitlines()) == count, "invalid LAB snapshot")
        result[table] = {"rows": count, "sha256": sha(raw)}
    metadata = query("""
SELECT jsonb_build_object(
 'columns',(SELECT jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position)
 FROM (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default
 FROM information_schema.columns WHERE table_schema='aiops') c),
 'constraints',(SELECT jsonb_agg(to_jsonb(c) ORDER BY rel, name)
 FROM (SELECT conrelid::regclass::text rel,conname name,pg_get_constraintdef(oid) definition
 FROM pg_constraint WHERE connamespace='aiops'::regnamespace) c),
 'indexes',(SELECT jsonb_agg(to_jsonb(i) ORDER BY tablename,indexname)
 FROM (SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='aiops') i)
)::text;
""")
    require(bool(metadata) and len(metadata) <= MAX_BYTES, "invalid schema projection")
    return {"tables": result, "schema_sha256": sha(metadata)}


def prove(docker, compose, root, bom, project):
    require(os.getenv("GITHUB_ACTIONS")=="true" and os.getenv("RUNNER_ENVIRONMENT")=="github-hosted"
            and os.getenv("V3_PG_RESTORE_CHECK")=="1" and os.getuid()!=0
            and root==Path("/tmp/aiops-v3-rootless-ci")
            and root.resolve()==root and project=="v3-e17-pinned-runtime-ci"
            and bom["production_authorized"] is False, "disposable E17 restore only")
    ref = bom["images"]["postgres"]["reference"]
    require(re.fullmatch(r"127\.0\.0\.1:15080/aiops-v3/postgres@sha256:[a-f0-9]{64}",ref), "wrong PostgreSQL image")
    # Stop writers after all E17 and browser proofs have completed. This is a
    # quiesced application DB check, not an atomic multi-store backup.
    compose("stop", *WRITERS)
    source = compose("ps","-q","postgres").decode().strip()
    require(re.fullmatch(r"[a-f0-9]{12,64}",source),"missing source database")
    psql_args = ("psql","-X","-qAt","-v","ON_ERROR_STOP=1","-U","aiops","-d","aiops")
    def source_query(sql):
        return compose("exec","-T","postgres",*psql_args,data=("SET TIME ZONE 'UTC';\n"+sql).encode())
    before = snapshot(source_query)
    require(all(before["tables"][t]["rows"]>0 for t in ("runs","run_events","evidence","gates")),
            "missing actual E17 application evidence")
    dump = compose("exec","-T","postgres","pg_dump","-Fc","--schema=aiops",
                   "--no-owner","--no-privileges","-U","aiops","-d","aiops")
    require(0<len(dump)<=MAX_BYTES,"invalid application dump")
    expected = sha(dump)
    compose("stop","postgres")
    state = json.loads(docker("inspect","--type","container",source))[0]
    require(state["State"]["Running"] is False,"source database still running")
    name = project+"-restore-pg"
    volume = name+"-data"
    require(name not in docker("container","ls","-a","--format","{{.Names}}").decode().splitlines()
            and volume not in docker("volume","ls","--format","{{.Name}}").decode().splitlines(),"restore destination exists")
    envfile = root/"e17-restore-pg.env"
    fd=os.open(envfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        f.write("POSTGRES_USER=aiops\nPOSTGRES_DB=aiops\nPOSTGRES_PASSWORD="+secrets.token_hex(24)+"\n")
    created_volume=False
    cid=None
    try:
        docker("volume","create","--label","com.docker.compose.project="+project,volume)
        created_volume=True
        cid=docker("run","-d","--pull","never","--network","none","--name",name,
                   "--env-file",str(envfile),"--mount",f"type=volume,source={volume},target=/var/lib/postgresql/data",
                   ref).decode().strip()
        require(re.fullmatch(r"[a-f0-9]{64}",cid) and not cid.startswith(source),"destination identity invalid")
        info=json.loads(docker("inspect","--type","container",cid))[0]
        require(info["Image"]==bom["images"]["postgres"]["engine_image_id"]
                and info["HostConfig"]["NetworkMode"]=="none"
                and not info["HostConfig"]["PortBindings"],"unsafe restore container")
        for _ in range(60):
            try:
                docker("exec",cid,"pg_isready","-h","127.0.0.1","-U","aiops","-d","aiops",timeout=5)
                break
            except ValueError:
                time.sleep(1)
        else:
            raise ValueError("destination database not ready")
        def dest_query(sql):
            return docker("exec","-i",cid,*psql_args,data=("SET TIME ZONE 'UTC';\n"+sql).encode())
        def restore(raw, expected_sha):
            require(0<len(raw)<=MAX_BYTES and sha(raw)==expected_sha,"backup digest mismatch")
            require(dest_query("SELECT count(*) FROM pg_namespace WHERE nspname='aiops';").strip()==b"0",
                    "restore destination not empty")
            docker("exec","-i",cid,"pg_restore","--exit-on-error","--single-transaction","--no-owner",
                   "--no-privileges","-U","aiops","-d","aiops",data=raw)
        try:
            restore(dump,"sha256:"+"0"*64)
        except ValueError as exc:
            require(str(exc)=="backup digest mismatch","wrong digest rejection failure")
        else:
            raise ValueError("wrong digest accepted")
        restore(dump,expected)
        after=snapshot(dest_query)
        require(before==after,"application schema or rows differ")
        try:
            restore(dump,expected)
        except ValueError as exc:
            require(str(exc)=="restore destination not empty","overwrite rejection failure")
        else:
            raise ValueError("existing restore destination accepted")
        require(snapshot(dest_query)==after,"overwrite refusal mutated state")
        receipt={"classification":"V3_E17_APPLICATION_PG_RESTORE","result":"PASS",
                 "source_sha":bom["source_sha"],"backup_sha256":expected,"backup_bytes":len(dump),
                 "source_stopped":True,"writers_stopped":True,"distinct_volume":True,
                 "wrong_digest_refused":True,"overwrite_refused":True,"snapshot":after,
                 "tables":len(TABLES),"rows":sum(x["rows"] for x in after["tables"].values()),
                 "temporal_restore":"NOT_RUN","collector_authority_restore":"NOT_RUN",
                 "same_daemon":True,"production_authorized":False}
        (root/"e17-application-pg-restore.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
        print(json.dumps(receipt,sort_keys=True))
    finally:
        try:
            if cid and re.fullmatch(r"[a-f0-9]{64}",cid):
                docker("rm","-f",cid)
        finally:
            try:
                if created_volume:
                    docker("volume","rm",volume)
            finally:
                envfile.unlink()
