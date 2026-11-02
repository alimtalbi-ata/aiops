#!/usr/bin/env python3
"""Fixed, non-destructive Debian poller probe; sidecar published via existing SSH checkout."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = Path.home() / ".local/state/aiops-debian-agent"
REPORT_GIT = STATE / "report-git"
BRANCH = "ops/debian-runtime-reports"
TARGET = "ops/debian-reports/SRV-DEB-05/poller-qualification.json"
LATEST_TARGET = "ops/debian-reports/SRV-DEB-05/latest.json"
LOCAL_LATEST = STATE / "latest.json"
DEV = Path("/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e")
POLLER = Path("/home/aiops/aiops2-auto-deploy/poll.sh")
REMOTE = "git@github.com:alimtalbi-ata/aiops.git"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
ID64 = re.compile(r"[0-9a-f]{64}\Z")
PORTS = (7777, 17777, 17778)


def run(argv, timeout=12):
    try:
        # Reuse existing report publisher's noninteractive SSH boundary.
        env = dict(os.environ, GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=10",
                   GIT_TERMINAL_PROMPT="0") if argv and argv[0] == "git" else None
        p = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout, env=env)
        return p.stdout.strip() if p.returncode == 0 and len(p.stdout) <= 131072 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def sha(path, runner=run):
    value = runner(["git", "-C", str(path), "rev-parse", "HEAD"])
    return value if isinstance(value, str) and SHA40.fullmatch(value) else None


def inspect(name, runner=run):
    raw = runner(["docker", "inspect", "--type", "container", name])
    try:
        data = json.loads(raw) if raw else []
        if not isinstance(data, list) or len(data) != 1:
            return {"inspection": "UNKNOWN"}
        obj = data[0]
        state = obj.get("State") or {}
        cfg = obj.get("Config") or {}
        host = obj.get("HostConfig") or {}
        labels = cfg.get("Labels") or {}
        binds = []
        for cp, entries in (host.get("PortBindings") or {}).items():
            if not isinstance(cp, str) or not re.fullmatch(r"[0-9]{1,5}/tcp", cp):
                continue
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                hp, ip = entry.get("HostPort"), entry.get("HostIp")
                if isinstance(hp, str) and hp.isdecimal() and int(hp) in PORTS and isinstance(ip, str) and re.fullmatch(r"[0-9a-fA-F:.]{1,64}", ip):
                    binds.append({"container_port": cp, "host_port": int(hp), "host_ip": ip})
        image = obj.get("Image")
        image = image if isinstance(image, str) and SHA256.fullmatch(image) else None
        digests = []
        if image:
            raw_digests = runner(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image])
            for item in (json.loads(raw_digests) if raw_digests else []) or []:
                if isinstance(item, str) and "@sha256:" in item:
                    digest = "sha256:" + item.rsplit("@sha256:", 1)[-1]
                    if SHA256.fullmatch(digest):
                        digests.append(digest)
        project = labels.get("com.docker.compose.project")
        cid = obj.get("Id")
        status = state.get("Status")
        health = (state.get("Health") or {}).get("Status")
        return {
            "inspection": "READ_ONLY",
            "container_id": cid if isinstance(cid, str) and ID64.fullmatch(cid) else None,
            "image_id": image, "manifest_digests": sorted(set(digests))[:8],
            "state": status if status in ("running", "exited", "paused", "restarting") else "UNKNOWN",
            "health": health if health in ("healthy", "unhealthy", "starting") else "UNKNOWN",
            "compose_project": project if project in ("aiops2-rebuild", "aiops2") else "UNKNOWN",
            "bindings": sorted(binds, key=lambda b: (b["host_port"], b["container_port"]))[:24],
            "mount_count": len(obj.get("Mounts") or []),
            "network_count": len((obj.get("NetworkSettings") or {}).get("Networks") or {}),
        }
    except (TypeError, ValueError, AttributeError, KeyError):
        return {"inspection": "UNKNOWN"}


def http():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:7777/health", timeout=5) as response:
            code, body = response.status, response.read(4097)
        if code != 200 or len(body) > 4096:
            return {"status": code, "qualified": False}
        obj = json.loads(body)
        return {"status": 200, "qualified": isinstance(obj, dict) and obj.get("status") == "ok" and type(obj.get("external_port")) is int and obj["external_port"] == 7777}
    except (OSError, ValueError, TypeError):
        return {"status": None, "qualified": False}


def tcp(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def poller():
    try:
        raw = POLLER.read_bytes()
        if len(raw) > 16384:
            return {"observed": False}
        return {"observed": True, "sha256": hashlib.sha256(raw).hexdigest(),
                "mentions_stable": b"deploy/aiops2-stable" in raw,
                "mentions_entrypoint": b"deploy-demo-studio-v2.sh" in raw}
    except OSError:
        return {"observed": False}


def collect(runner=run, http_probe=http, tcp_probe=tcp, clock=None):
    portal = inspect("aiops2-rebuild-portal", runner)
    candidate = inspect("aiops2-portal-candidate-web-20261029", runner)
    h = http_probe()
    good = (portal.get("state") == "running" and portal.get("health") == "healthy"
            and portal.get("compose_project") == "aiops2-rebuild"
            and any(b["host_port"] == 7777 for b in portal.get("bindings", []))
            and h.get("qualified") is True)
    return {
        "schema": "aiops.debian-poller-qualification.v1",
        "collected_at": (clock or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc).isoformat(),
        "execution": "POLLER_ENTRYPOINT_READONLY" if runner is run else "TEST_FIXTURE",
        "stable_checkout_sha": sha(ROOT, runner), "dev_checkout_sha": sha(DEV, runner),
        "poller": poller() if runner is run else {"observed": False},
        "portal": portal, "candidate_portal": candidate,
        "http_7777": h, "tcp_loopback": {str(p): bool(tcp_probe(p)) for p in PORTS},
        "host_portal_7777": "PASS" if good else "FAIL_OR_UNKNOWN",
        "external_tls_sso_glpi_e2e": "NOT_VERIFIED",
        "single_public_portal": "NOT_VERIFIED",
        "release_stable": "NO_GO", "docker_mutations": 0,
    }



def validated_fresh_local_report(path, now=None):
    """One-shot recovery of the existing publisher's already-public, bounded schema.

    Never copy arbitrary local JSON into a public GitHub repository. This is
    NOT a replacement for the recurring SSH publisher cron.
    """
    try:
        if path.stat().st_size > 32768:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"agent", "collected_at", "docker", "host", "resources",
                    "schema_version", "tcp_loopback"}
        if type(data) is not dict or set(data) != required:
            return None
        if data["schema_version"] != 1 or data["agent"] != {
                "name": "aiops-debian-readonly", "version": "1.0.0"}:
            return None
        when = dt.datetime.fromisoformat(data["collected_at"].replace("Z", "+00:00"))
        if when.tzinfo is None:
            return None
        age = (now or dt.datetime.now(dt.timezone.utc)) - when
        if not 0 <= age.total_seconds() <= 900:
            return None
        docker = data["docker"]
        if (type(docker) is not dict or set(docker) !=
                {"available", "containers", "truncated"} or
                type(docker["containers"]) is not list or
                len(docker["containers"]) > 128):
            return None
        for item in docker["containers"]:
            if (type(item) is not dict or
                    not set(item).issubset({"name", "image", "state", "health", "inspect_ok"}) or
                    not {"name", "image", "state", "health", "inspect_ok"}.issubset(item) or
                    any(type(item[k]) is not str or len(item[k]) > 256
                        for k in ("name", "image", "state", "health")) or
                    type(item["inspect_ok"]) is not bool):
                return None
        if (type(data["host"]) is not dict or
                not set(data["host"]).issubset(
                    {"architecture", "kernel", "os", "reported_name", "uptime"}) or
                type(data["resources"]) is not dict or
                not set(data["resources"]).issubset(
                    {"disk_home", "disk_root", "load_1_5_15", "memory_bytes"}) or
                type(data["tcp_loopback"]) is not dict or
                not set(data["tcp_loopback"]).issubset(
                    {"3000", "5432", "7233", "9090", "17777", "7777", "17778"})):
            return None
        # No unexpected key names at any nesting depth, including secrets.
        def suspicious(obj):
            if isinstance(obj, dict):
                return any(re.search(r"token|password|secret|authorization|api.?key|private.?key", str(k), re.I)
                           or suspicious(v) for k, v in obj.items())
            if isinstance(obj, list):
                return any(suspicious(v) for v in obj)
            return False
        if suspicious(data):
            return None
        output = json.dumps(data, sort_keys=True, indent=2) + "\n"
        return output if len(output.encode("utf-8")) <= 32768 else None
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return None


def publish(report, runner=run):
    """Never overwrite minute reporter latest.json; use its SSH checkout and lock."""
    if not (REPORT_GIT / ".git").is_dir():
        raise RuntimeError("report_checkout_missing")
    with (STATE / "publish.lock").open("a+") as lock:
        for attempt in range(20):
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if attempt == 19:
                    raise RuntimeError("publisher_busy")
                time.sleep(1)
        base = ["git", "-C", str(REPORT_GIT)]
        if runner(base + ["remote", "get-url", "origin"]) != REMOTE:
            raise RuntimeError("unexpected_remote")
        if runner(base + ["status", "--porcelain"]) != "":
            raise RuntimeError("dirty_checkout")
        for cmd in (["fetch", "--quiet", "origin", BRANCH],
                    ["checkout", "--quiet", BRANCH],
                    ["merge", "--ff-only", "--quiet", "origin/" + BRANCH]):
            if runner(base + cmd) is None:
                raise RuntimeError("report_git_sync_failed")
        target = REPORT_GIT / TARGET
        target.parent.mkdir(parents=True, exist_ok=True)
        # Existing minute reporter writes a separate local file; the SSH
        # publisher cron is currently stale. Recover ONE fresh validated
        # snapshot through this already-qualified Git writer under same lock.
        local_latest = validated_fresh_local_report(LOCAL_LATEST)
        if local_latest is not None:
            latest_target = REPORT_GIT / LATEST_TARGET
            latest_tmp = latest_target.with_suffix(".tmp")
            latest_tmp.write_text(local_latest, encoding="utf-8")
            latest_tmp.chmod(0o600)
            latest_tmp.replace(latest_target)
        content = json.dumps(report, sort_keys=True, indent=2) + "\n"
        if len(content.encode()) > 16384:
            raise RuntimeError("receipt_oversize")
        temp = target.with_suffix(".tmp")
        temp.write_text(content)
        temp.chmod(0o600)
        temp.replace(target)
        staged = [TARGET] + ([LATEST_TARGET] if local_latest is not None else [])
        if runner(base + ["add", "--"] + staged) is None:
            raise RuntimeError("report_add_failed")
        if runner(base + ["diff", "--cached", "--quiet"]) is not None:
            return "UNCHANGED"
        if runner(base + ["-c", "user.name=AIOps2 Debian Poller",
                          "-c", "user.email=aiops2-poller@users.noreply.github.com",
                          "commit", "--quiet", "-m", "ops(debian): read-only poller qualification"]) is None:
            raise RuntimeError("report_commit_failed")
        if runner(base + ["push", "--quiet", "origin", "HEAD:refs/heads/" + BRANCH], timeout=20) is None:
            raise RuntimeError("report_push_failed")
        return "PUBLISHED"


def main():
    try:
        result = publish(collect())
        print("AIOPS_DEBIAN_POLLER_RECEIPT=" + result)
        return 0
    except Exception as exc:
        print("AIOPS_DEBIAN_POLLER_RECEIPT=FAILED reason=" + type(exc).__name__, file=sys.stderr)
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
