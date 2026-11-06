#!/usr/bin/env python3
"""FS1085 revised rollout; requires separate explicit approval."""
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
import urllib.error

if os.environ.get("FS1085_EXPLICIT_APPROVAL") != "YES":
    raise SystemExit("FS1085_NOT_AUTHORIZED: separate production approval required")

NAME="aiops2-rebuild-portal"
IMAGE="aiops2-portal:fs1073-csp-candidate"
ROOT=pathlib.Path.home()
STAMP=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
OLD=NAME+"-fs1085-rollback-"+STAMP
BACKUP=ROOT/("aiops2-portal-fs1085-backup-"+STAMP)
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

def wait_for_readiness():
    expected={"aiops2-rebuild-control","aiops2-rebuild-integration","aiops2-rebuild-public"}
    last="unavailable"
    for attempt in range(1,61):
        state=inspect(NAME)
        if not state["State"]["Running"]:
            raise RuntimeError("FS1085_CANDIDATE_EXITED")
        nets=set(state["NetworkSettings"]["Networks"])
        mapped=(state["NetworkSettings"].get("Ports") or {}).get("777/tcp") or []
        effective=any(p.get("HostPort")=="7777" for p in mapped)
        if nets==expected and effective:
            try:
                with urllib.request.urlopen("http://127.0.0.1:7777/health",timeout=3) as r:
                    if r.status==200:
                        print("FS1085_NETWORK_GATE=PASS ATTEMPT="+str(attempt),flush=True)
                        return
                    last="HTTP "+str(r.status)
            except (urllib.error.URLError,TimeoutError,ConnectionError,OSError) as exc:
                last=type(exc).__name__
        else:
            last="networks="+str(nets==expected)+" effective_port="+str(effective)
        time.sleep(1)
    raise RuntimeError("FS1085_READINESS_TIMEOUT "+last)

def check_http(path):
    last="unavailable"
    for _ in range(10):
        try:
            with urllib.request.urlopen("http://127.0.0.1:7777"+path,timeout=3) as r:
                if r.status==200:
                    print("FS1085_HTTP="+path+" STATUS=200",flush=True)
                    return
                last=str(r.status)
        except (urllib.error.URLError,TimeoutError,ConnectionError,OSError) as exc:
            last=type(exc).__name__
        time.sleep(1)
    raise RuntimeError("FS1085_HTTP_FAILED "+path+" last="+last)

def check_visual_csp():
    with urllib.request.urlopen("http://127.0.0.1:7777/explorer/visual",timeout=5) as response:
        assert response.status==200, "visual status not 200"
        policies=response.headers.get_all("Content-Security-Policy") or []
        assert len(policies)==1, "unexpected CSP header count"
        policy=policies[0]
        assert policy.count("sha256-")>=2, "missing script/style hashes"
        assert "script-src" in policy and "style-src" in policy and "connect-src 'self'" in policy, "missing CSP directives"
        assert "unsafe-inline" not in policy, "unsafe inline CSP"
        html=response.read(100000)
        assert b'id="graph"' in html and b'id="targets"' in html, "visual markup missing"
    print("FS1085_VISUAL_CSP=PASS",flush=True)

def check_visual_api(path,required):
    with urllib.request.urlopen("http://127.0.0.1:7777"+path,timeout=8) as response:
        assert response.status==200, "API not 200"
        data=json.loads(response.read(3000000))
    assert all(k in data for k in required), "API schema missing keys"
    print("FS1085_API="+path+" STATUS=200",flush=True)

def rollback():
    print("FS1085_ROLLBACK=START",flush=True)
    try:
        docker("rm","-f",NAME,check=False)
        if renamed:
            docker("rename",OLD,NAME)
            if old_was_running:
                docker("update","--restart=unless-stopped",NAME)
                docker("start",NAME)
            print("FS1085_ROLLBACK=RESTORED",flush=True)
        else:
            print("FS1085_ROLLBACK=NOT_REQUIRED",flush=True)
    except Exception as exc:
        print("FS1085_ROLLBACK=FAILED "+str(exc),flush=True)

try:
    source=inspect(NAME)
    assert source["State"]["Running"], "portal not running"
    old_was_running=True
    assert source["Config"]["Image"]=="aiops2-portal:fs1051-visual-candidate", "unexpected production image"
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
    print("FS1085_PREFLIGHT=PASS",flush=True)
    print("FS1085_BACKUP_DIR="+str(BACKUP),flush=True)
    print("FS1085_OLD_CONTAINER="+OLD,flush=True)
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
        wait_for_readiness()
        for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual"):
            check_http(path)
        check_visual_csp()
        check_visual_api("/api/fs1051/prometheus",("up","down","targets"))
        check_visual_api("/api/fs1051/twin",("nodes","edges"))
        print("FS1085_DEPLOY=PASS",flush=True)
        print("FS1085_ROLLBACK_CONTAINER="+OLD,flush=True)
    except Exception:
        rollback()
        renamed=False
        raise
    finally:
        # Avoid keeping plaintext secrets in a second location.
        envfile.unlink(missing_ok=True)
except Exception as exc:
    if not renamed and old_was_running:
        try:
            state=inspect(NAME)
            if not state["State"]["Running"]:
                docker("update","--restart=unless-stopped",NAME)
                docker("start",NAME)
                print("FS1085_ORIGINAL_CONTAINER=RESTORED",flush=True)
        except Exception as recovery_error:
            print("FS1085_ORIGINAL_CONTAINER=RECOVERY_FAILED "+str(recovery_error),flush=True)
    print("FS1085_DEPLOY=FAIL "+str(exc),flush=True)
    sys.exit(1)
