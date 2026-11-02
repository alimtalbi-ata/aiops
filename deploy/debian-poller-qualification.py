#!/usr/bin/env python3
"""Fixed, non-destructive Debian poller probe; sidecar published via existing SSH checkout."""
import datetime as dt
import fcntl
import hashlib
import json
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
DEV = Path("/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e")
POLLER = Path("/home/aiops/aiops2-auto-deploy/poll.sh")
REMOTE = "git@github.com:alimtalbi-ata/aiops.git"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
ID64 = re.compile(r"[0-9a-f]{64}\Z")
PORTS = (7777, 17777, 17778)


def run(argv, timeout=12):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)
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
        content = json.dumps(report, sort_keys=True, indent=2) + "\n"
        if len(content.encode()) > 16384:
            raise RuntimeError("receipt_oversize")
        temp = target.with_suffix(".tmp")
        temp.write_text(content)
        temp.chmod(0o600)
        temp.replace(target)
        if runner(base + ["add", "--", TARGET]) is None:
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
