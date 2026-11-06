#!/usr/bin/env python3
"""FS1053 authorized native Docker portal replacement, with rollback."""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

NAME="aiops2-rebuild-portal"
IMAGE="aiops2-portal:fs1051-visual-candidate"
ROOT=pathlib.Path.home()
STAMP=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
OLD=NAME+"-fs1053-rollback-"+STAMP
BACKUP=ROOT/("aiops2-portal-fs1053-backup-"+STAMP)
BACKUP.mkdir(mode=0o700)
os.chmod(BACKUP,0o700)
replaced=False
renamed=False
old_was_running=False

def docker(*args, capture=True, check=True):
    p=subprocess.run(["docker",*map(str,args)],text=True,stdout=subprocess.PIPE if capture else subprocess.DEVNULL,stderr=subprocess.PIPE)
    if check and p.returncode:
        raise RuntimeError("docker command failed: "+str(args[:2])+"; "+p.stderr[-400:])
    return p.stdout.strip() if capture else p.returncode==0

def inspect(name):
    return json.loads(docker("inspect",name))[0]

def check_http(path):
    url="http://127.0.0.1:7777"+path
    last="unavailable"
    for _ in range(20):
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                if r.status==200:
                    print("FS1053_HTTP="+path+" STATUS=200",flush=True)
                    return
                last=str(r.status)
        except (urllib.error.URLError,TimeoutError) as exc:
            last=type(exc).__name__
        time.sleep(1)
    raise RuntimeError("health check failed "+path+" last="+last)

def rollback():
    print("FS1053_ROLLBACK=START",flush=True)
    try:
        docker("rm","-f",NAME,check=False)
        if renamed:
            docker("rename",OLD,NAME)
            if old_was_running:
                docker("update","--restart=unless-stopped",NAME)
                docker("start",NAME)
            print("FS1053_ROLLBACK=RESTORED",flush=True)
        else:
            print("FS1053_ROLLBACK=NOT_REQUIRED",flush=True)
    except Exception as exc:
        print("FS1053_ROLLBACK=FAILED "+str(exc),flush=True)

try:
    source=inspect(NAME)
    assert source["State"]["Running"], "portal not running"
    old_was_running=True
    assert source["Config"]["Image"]=="aiops2-portal:fs1040-sql-guard-candidate", "unexpected production image"
    docker("image","inspect",IMAGE)
    host=source["HostConfig"]
    assert host["NetworkMode"] not in ("host","container","none"), "unsupported network mode"
    ports=host.get("PortBindings") or {}
    assert ports.get("777/tcp"), "expected container port 777"
    assert any(p.get("HostPort")=="7777" for p in ports["777/tcp"]), "expected host port 7777"
    assert set(ports)=={"777/tcp"}, "unexpected additional port mappings"
    mounts=source.get("Mounts",[])
    assert all(m["Type"] in ("volume","bind") for m in mounts), "unsupported mount"
    assert all(m.get("RW",False) for m in mounts), "unexpected read-only mount"
    networks=source["NetworkSettings"]["Networks"]
    expected={"aiops2-rebuild-control","aiops2-rebuild-integration","aiops2-rebuild-public"}
    assert set(networks)==expected, "network mismatch"
    assert not host.get("Privileged"), "unexpected privileged container"
    assert not host.get("Devices"), "unexpected device mappings"
    assert not host.get("CapAdd"), "unexpected extra capabilities"
    assert not host.get("Dns"), "custom DNS needs manual review"
    assert not host.get("ExtraHosts"), "custom extra hosts need manual review"
    assert not source["Config"].get("Entrypoint") or isinstance(source["Config"]["Entrypoint"],list)
    assert host.get("RestartPolicy",{}).get("Name")=="unless-stopped", "unexpected restart policy"
    assert not host.get("Binds") or all(m["Type"] in ("volume","bind") for m in mounts)
    for name in expected: docker("network","inspect",name)
    # Backup includes secrets: owner-only directory and files. Never print their contents.
    config_path=BACKUP/"container-inspect.json"
    fd=os.open(config_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as out: json.dump(source,out,indent=2)
    print("FS1053_PREFLIGHT=PASS",flush=True)
    print("FS1053_BACKUP_DIR="+str(BACKUP),flush=True)
    print("FS1053_OLD_CONTAINER="+OLD,flush=True)
    envfile=BACKUP/"environment.env"
    fd=os.open(envfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as out:
        for item in source["Config"].get("Env",[]):
            assert "\n" not in item and "\r" not in item, "multiline env unsupported"
            out.write(item+"\n")
    args=["run","-d","--name",NAME,"--restart","unless-stopped","--network","aiops2-rebuild-integration","--env-file",str(envfile)]
    cfg=source["Config"]
    if cfg.get("User"): args+=["--user",cfg["User"]]
    if cfg.get("WorkingDir"): args+=["--workdir",cfg["WorkingDir"]]
    if cfg.get("Hostname") and cfg["Hostname"] != source["Id"][:12]:
        # Container-generated hostname is not a stable contract.
        pass
    for key,value in (cfg.get("Labels") or {}).items():
        args+=["--label",key+"="+value]
    for mount in mounts:
        src=mount["Name"] if mount["Type"]=="volume" else mount["Source"]
        spec="type="+mount["Type"]+",src="+src+",dst="+mount["Destination"]
        args+=["--mount",spec]
    for port,bindings in ports.items():
        for bind in bindings:
            host_ip=bind.get("HostIp") or "0.0.0.0"
            args+=["-p",host_ip+":"+bind["HostPort"]+":"+port]
    if cfg.get("Entrypoint"):
        assert len(cfg["Entrypoint"])==1, "multi-part entrypoint requires review"
        args+=["--entrypoint",cfg["Entrypoint"][0]]
    args.append(IMAGE)
    args.extend(cfg.get("Cmd") or [])
    # Disable old restart before stopping to ensure it cannot contend for port.
    docker("update","--restart=no",NAME)
    docker("stop","--time","20",NAME)
    docker("rename",NAME,OLD)
    renamed=True
    try:
        docker(*args)
        replaced=True
        for network in ("aiops2-rebuild-control","aiops2-rebuild-public"):
            docker("network","connect",network,NAME)
        for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual"):
            check_http(path)
        print("FS1053_DEPLOY=PASS",flush=True)
        print("FS1053_ROLLBACK_CONTAINER="+OLD,flush=True)
    except Exception:
        rollback()
        renamed=False
        raise
    finally:
        # Avoid keeping plaintext secrets in a second location.
        envfile.unlink(missing_ok=True)
except Exception as exc:
    print("FS1053_DEPLOY=FAIL "+str(exc),flush=True)
    sys.exit(1)
