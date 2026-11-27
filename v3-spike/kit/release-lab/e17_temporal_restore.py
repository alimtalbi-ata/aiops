"""Restore actual E17 Temporal persistence and visibility in an isolated fresh LAB stack.
No activity worker is started. Only the existing verified history projection is read.
Not a general backup, an atomic multi-store recovery, or a production procedure.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time

DATABASES = ("temporal", "temporal_visibility")
ROOT = Path("/tmp/aiops-v3-rootless-ci")
MAX_BYTES = 64 * 1024**2


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical_schema(metadata):
    """Preserve visible column order, not physical attnum gaps left by DROP COLUMN."""
    schema = json.loads(metadata)
    require(set(schema) == {"columns", "constraints", "indexes"}, "unexpected Temporal schema projection")
    columns = schema["columns"]
    fields = {"table_name", "column_name", "ordinal_position", "data_type", "udt_name",
              "is_nullable", "column_default"}
    require(isinstance(columns, list) and 0 < len(columns) <= 4096, "invalid columns projection")
    ranks, last, seen, physical = {}, {}, set(), []
    logical = []
    for col in columns:
        require(isinstance(col, dict) and set(col) == fields, "invalid column projection")
        table, name, pos = col["table_name"], col["column_name"], col["ordinal_position"]
        require(isinstance(table, str) and isinstance(name, str) and type(pos) is int
                and pos > last.get(table, 0) and (table, name) not in seen, "invalid physical column order")
        seen.add((table, name))
        last[table] = pos
        ranks[table] = ranks.get(table, 0) + 1
        physical.append([table, name, pos])
        logical.append(dict(col, ordinal_position=ranks[table]))
    normalized = dict(schema, columns=logical)
    def digest(value):
        return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
    return {"schema_sha256": digest(normalized),
            "schema_components": {name: digest(value) for name, value in normalized.items()},
            "column_fields": {field: digest([col[field] for col in logical]) for field in sorted(fields)},
            "physical_ordinal_sha256": digest(physical)}


def snapshot(query, db):
    names = query(db, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename COLLATE \"C\";").decode().splitlines()
    require(0 < len(names) <= 128 and len(set(names)) == len(names), "unexpected Temporal schema")
    rows = {}
    total = 0
    for name in names:
        require(re.fullmatch(r"[a-z_][a-z_0-9]*", name), "unexpected table identifier")
        raw = query(db, 'SELECT to_jsonb(t)::text FROM public.' + name + ' t ORDER BY to_jsonb(t)::text COLLATE "C";')
        count = int(query(db, "SELECT count(*) FROM public."+name+";"))
        total += len(raw)
        require(total <= MAX_BYTES and len(raw.splitlines()) == count, "invalid Temporal row snapshot")
        rows[name] = {"rows": count, "sha256": sha(raw)}
    require(sum(v["rows"] for v in rows.values()) > 0, "empty Temporal database")
    metadata = query(db, """
SELECT jsonb_build_object(
 'columns',(SELECT jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position)
 FROM (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default
 FROM information_schema.columns WHERE table_schema='public') c),
 'constraints',(SELECT jsonb_agg(to_jsonb(c) ORDER BY rel,name)
 FROM (SELECT conrelid::regclass::text rel,conname name,pg_get_constraintdef(oid) definition
 FROM pg_constraint WHERE connamespace='public'::regnamespace) c),
 'indexes',(SELECT jsonb_agg(to_jsonb(i) ORDER BY tablename,indexname)
 FROM (SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public') i)
)::text;
""")
    require(bool(metadata) and len(metadata) <= MAX_BYTES, "invalid Temporal schema projection")
    return {"tables": rows, **canonical_schema(metadata)}


def require_equal_snapshots(before, after, phase):
    """Report bounded structural differences, never row payloads or SQL definitions."""
    if before == after:
        return
    # pg_dump/restore may compact dropped-column attnum gaps. Allow only that
    # physical difference, only on the fresh restore, and record it explicitly.
    def logical(value):
        return {key: item for key, item in value.items() if key != "physical_ordinal_sha256"}
    if phase == "after_restore_before_server_start" and all(
            logical(before[db]) == logical(after[db]) for db in DATABASES):
        print(json.dumps({"classification": "V3_E17_TEMPORAL_PHYSICAL_ORDINAL_NORMALIZATION",
                          "phase": phase, "result": "PASS_LOGICAL_SCHEMA",
                          "databases": [db for db in DATABASES if before[db] != after[db]]},
                         sort_keys=True), flush=True)
        return
    differences = []
    for db in DATABASES:
        left, right = before[db], after[db]
        tables = []
        for name in sorted(left["tables"].keys() | right["tables"].keys()):
            a, b = left["tables"].get(name), right["tables"].get(name)
            if a != b:
                tables.append({"table": name, "before_rows": None if a is None else a["rows"],
                               "after_rows": None if b is None else b["rows"],
                               "row_digest_changed": a is not None and b is not None and a["sha256"] != b["sha256"]})
        components = sorted(name for name in left["schema_components"]
                            if left["schema_components"][name] != right["schema_components"][name])
        if left != right:
            differences.append({"database": db, "tables": tables,
                                "schema_digest_changed": left["schema_sha256"] != right["schema_sha256"],
                                "schema_components_changed": components,
                                "column_fields_changed": sorted(name for name in left["column_fields"]
                                    if left["column_fields"][name] != right["column_fields"][name]),
                                "physical_ordinals_changed": left["physical_ordinal_sha256"] != right["physical_ordinal_sha256"]})
    print(json.dumps({"classification": "V3_E17_TEMPORAL_SNAPSHOT_DIFFERENCE",
                      "phase": phase, "result": "FAIL", "differences": differences}, sort_keys=True), flush=True)
    raise ValueError("Temporal snapshot mismatch: " + phase)


def prove(docker, compose, root, bom, project, report, history_probe, history):
    require(os.getenv("GITHUB_ACTIONS")=="true" and os.getenv("RUNNER_ENVIRONMENT")=="github-hosted"
            and os.getenv("V3_TEMPORAL_RESTORE_CHECK")=="1" and os.getenv("V3_PG_RESTORE_CHECK")=="1"
            and os.getuid()!=0 and root==ROOT and root.resolve()==root
            and project=="v3-e17-pinned-runtime-ci" and bom["production_authorized"] is False,
            "disposable E17 restore only")
    app=json.loads((root/"e17-application-pg-restore.json").read_text())
    require(app["result"]=="PASS" and app["writers_stopped"] is True and app["source_stopped"] is True
            and app["source_sha"]==bom["source_sha"], "application quiesce proof required")
    parsed=json.loads(report)
    projected=json.loads(history)
    require(projected["workflow_id"]==parsed["workflow_id"]
            and projected["action_receipt_sha256"]==parsed["action_receipt_sha256"]
            and projected["production_authorized"] is False, "wrong original history")
    def image(service):
        value=bom["images"][service]["reference"]
        require(re.fullmatch(r"127\.0\.0\.1:15080/aiops-v3/"+service+r"@sha256:[a-f0-9]{64}",value),
                "invalid pinned image")
        return value
    pg_ref,temporal_ref,reader_ref=map(image,("temporal-postgres","temporal","worker"))
    src=compose("ps","-q","temporal-postgres").decode().strip()
    require(re.fullmatch(r"[a-f0-9]{12,64}",src),"source database absent")
    compose("stop","temporal")
    def source_query(db,sql):
        return compose("exec","-T","temporal-postgres","psql","-X","-qAt","-v","ON_ERROR_STOP=1",
                       "-U","temporal","-d",db,data=("SET TIME ZONE 'UTC';\n"+sql).encode())
    inventory=source_query("postgres","SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname;")
    require(set(inventory.decode().splitlines())=={"postgres",*DATABASES},"unexpected Temporal databases")
    before={db:snapshot(source_query,db) for db in DATABASES}
    dumps={db:compose("exec","-T","temporal-postgres","pg_dump","-Fc","--no-owner","--no-privileges",
                      "-U","temporal","-d",db) for db in DATABASES}
    require(all(0<len(raw)<=MAX_BYTES for raw in dumps.values()),"invalid Temporal dump")
    expected={db:sha(raw) for db,raw in dumps.items()}
    compose("stop","temporal-postgres")
    require(json.loads(docker("inspect","--type","container",src))[0]["State"]["Running"] is False,
            "source persistence still running")
    names={kind:project+"-history-"+kind for kind in ("db","server","reader","net","data")}
    for kind,slots in (("container",("db","server","reader")),("volume",("data",)),("network",("net",))):
        existing=set(docker(kind,"ls",*(("-a",) if kind=="container" else ()),
                            "--format","{{.Names}}" if kind=="container" else "{{.Name}}").decode().splitlines())
        require(not existing.intersection(names[s] for s in slots),"restore destination exists")
    password=secrets.token_hex(24)
    pg_env=root/"e17-history-pg.env"
    server_env=root/"e17-history-server.env"
    created=[]
    created_files=[]
    volume=False
    network=False
    def envfile(path,values):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        created_files.append(path)
        with os.fdopen(fd,"w") as f:
            f.write("".join(k+"="+v+"\n" for k,v in values.items()))
    try:
        envfile(pg_env,{"POSTGRES_USER":"temporal","POSTGRES_DB":"temporal","POSTGRES_PASSWORD":password})
        envfile(server_env,{"DB":"postgres12","DB_PORT":"5432","POSTGRES_USER":"temporal",
                            "POSTGRES_PWD":password,"POSTGRES_SEEDS":"temporal-postgres",
                            "BIND_ON_IP":"0.0.0.0","SKIP_SCHEMA_SETUP":"true",
                            "SKIP_DEFAULT_NAMESPACE_CREATION":"true"})
        label="com.docker.compose.project="+project
        docker("network","create","--internal","--label",label,names["net"])
        network=True
        require(json.loads(docker("network","inspect",names["net"]))[0]["Internal"] is True,"restore network not isolated")
        docker("volume","create","--label",label,names["data"])
        volume=True
        def start(slot,service,*args):
            cid=docker("run","-d","--pull","never","--name",names[slot],"--label",label,
                       "--network",names["net"],*args,image(service)).decode().strip()
            require(re.fullmatch(r"[a-f0-9]{64}",cid),"invalid destination container identity")
            created.append(cid)
            info=json.loads(docker("inspect","--type","container",cid))[0]
            require(info["Image"]==bom["images"][service]["engine_image_id"] and
                    not info["HostConfig"]["PortBindings"] and
                    set(info["NetworkSettings"]["Networks"])=={names["net"]},"wrong destination isolation")
            return cid
        dbcid=start("db","temporal-postgres","--network-alias","temporal-postgres","--env-file",str(pg_env),
                    "--mount",f"type=volume,source={names['data']},target=/var/lib/postgresql/data")
        def wait(command):
            for _ in range(90):
                try:
                    docker(*command,timeout=10)
                    return
                except ValueError:
                    time.sleep(1)
            raise ValueError("restored service readiness timeout")
        wait(("exec",dbcid,"pg_isready","-h","127.0.0.1","-U","temporal","-d","temporal"))
        docker("exec",dbcid,"createdb","-U","temporal","temporal_visibility")
        def dest_query(db,sql):
            return docker("exec","-i",dbcid,"psql","-X","-qAt","-v","ON_ERROR_STOP=1","-U","temporal",
                          "-d",db,data=("SET TIME ZONE 'UTC';\n"+sql).encode())
        def restore(db,raw,d):
            require(db in DATABASES and 0<len(raw)<=MAX_BYTES and sha(raw)==d,"backup digest mismatch")
            require(dest_query(db,"SELECT count(*) FROM pg_tables WHERE schemaname='public';").strip()==b"0",
                    "Temporal destination not empty")
            docker("exec","-i",dbcid,"pg_restore","--exit-on-error","--single-transaction","--no-owner",
                   "--no-privileges","-U","temporal","-d",db,data=raw)
        try:
            restore("temporal",dumps["temporal"],"sha256:"+"0"*64)
        except ValueError as exc:
            require(str(exc)=="backup digest mismatch","incorrect digest refusal")
        else:
            raise ValueError("wrong digest accepted")
        for db in DATABASES:
            restore(db,dumps[db],expected[db])
        after={db:snapshot(dest_query,db) for db in DATABASES}
        require_equal_snapshots(before, after, "after_restore_before_server_start")
        try:
            restore("temporal",dumps["temporal"],expected["temporal"])
        except ValueError as exc:
            require(str(exc)=="Temporal destination not empty","incorrect overwrite refusal")
        else:
            raise ValueError("existing destination accepted")
        require_equal_snapshots(after, {db:snapshot(dest_query,db) for db in DATABASES}, "after_overwrite_refusal")
        server=start("server","temporal","--network-alias","temporal","--env-file",str(server_env))
        # The existing SDK readback below proves server readiness and the restored namespace;
        # do not assume the auto-setup image ships the standalone Temporal CLI.
        # Explicit entrypoint: no worker process, activity polling, or target access.
        probe=history_probe.decode()
        connect='    client=await asyncio.wait_for(Client.connect("temporal:7233"),timeout=10)'
        retry='    client=None\n    for _ in range(60):\n        try:\n            client=await asyncio.wait_for(Client.connect("temporal:7233"),timeout=5)\n            break\n        except Exception:\n            await asyncio.sleep(1)\n    require(client is not None,"restored Temporal server not ready")'
        require(probe.count(connect)==1,"unexpected Temporal SDK probe")
        probe=probe.replace(connect,retry)
        recovered=docker("run","--rm","-i","--pull","never","--name",names["reader"],
                         "--network",names["net"],"--cap-drop","ALL","--security-opt","no-new-privileges",
                         "--env","AIOPS_V3_BOUNDARY=1","--env","TEMPORAL_ADDRESS=temporal:7233",
                         "--entrypoint","python",reader_ref,"-c",probe,data=report,timeout=70)
        require(recovered==history,"restored history projection changed")
        receipt={"classification":"V3_E17_TEMPORAL_PERSISTENCE_RESTORE","result":"PASS",
                 "source_sha":bom["source_sha"],"workflow_id":parsed["workflow_id"],
                 "action_receipt_sha256":parsed["action_receipt_sha256"],"history_projection_sha256":sha(history),
                 "events":len(projected["events"]),"activity_attempt":projected["activity_attempt"],
                 "databases":{db:{"backup_sha256":expected[db],"backup_bytes":len(dumps[db]),
                                  "tables":len(after[db]["tables"]),"rows":sum(v["rows"] for v in after[db]["tables"].values()),
                                  "schema_sha256":after[db]["schema_sha256"],
                                  "source_physical_ordinal_sha256":before[db]["physical_ordinal_sha256"],
                                  "restored_physical_ordinal_sha256":after[db]["physical_ordinal_sha256"],
                                  "physical_ordinals_changed":before[db]["physical_ordinal_sha256"] != after[db]["physical_ordinal_sha256"],
                                  "snapshot_sha256":sha(json.dumps(after[db],sort_keys=True).encode())} for db in DATABASES},
                 "source_stopped":True,"fresh_volume":True,"same_daemon":True,"worker_started":False,
                 "wrong_digest_refused":True,"overwrite_refused":True,"history_projection_identical":True,
                 "raw_history_exported":False,"atomic_multistore_recovery":False,
                 "collector_authority_restore":"NOT_RUN","production_authorized":False}
        (root/"e17-temporal-restore.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
        print(json.dumps(receipt,sort_keys=True))
    finally:
        try:
            for cid in reversed(created):
                docker("rm","-f",cid)
        finally:
            try:
                if volume:
                    docker("volume","rm",names["data"])
                if network:
                    docker("network","rm",names["net"])
            finally:
                for path in created_files:
                    path.unlink()
