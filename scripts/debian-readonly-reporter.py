#!/usr/bin/env python3
"""AIOps2 Debian read-only reporter. Fixed probes only; no remote command execution."""
from __future__ import annotations
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from debian_runtime_probe import collect_runtime_contract

REPOSITORY = "alimtalbi-ata/aiops"
REPORT_BRANCH = "ops/debian-runtime-reports"
REPORT_PATH = "ops/debian-reports/SRV-DEB-05/latest.json"
TOKEN_PATH = Path.home() / ".config/aiops/github-token"
STATE_DIR = Path.home() / ".local/state/aiops-debian-agent"
LOCK_PATH = STATE_DIR / "agent.lock"
LATEST_PATH = STATE_DIR / "latest.json"
MAX_REPORT_BYTES = 64 * 1024
MAX_COMMAND_SECONDS = 8
GITHUB_API = "https://api.github.com"


def fixed_command(argv: list[str], timeout: int = MAX_COMMAND_SECONDS) -> dict:
    """Run one hard-coded diagnostic command; never invoke a shell."""
    try:
        p = subprocess.run(argv, text=True, capture_output=True, timeout=timeout, check=False)
        return {"available": True, "returncode": p.returncode,
                "stdout": p.stdout[:4000].strip(), "stderr": p.stderr[:1000].strip()}
    except FileNotFoundError:
        return {"available": False, "reason": "command_not_installed"}
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "timeout"}


def read_meminfo() -> dict:
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                values[key] = int(rest.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        return {}
    return values


def disk_info(path: str) -> dict:
    try:
        d = shutil.disk_usage(path)
        return {"total_bytes": d.total, "used_bytes": d.used, "free_bytes": d.free}
    except OSError:
        return {"available": False}


def docker_inventory() -> dict:
    names = fixed_command(["docker", "ps", "--all", "--format", "{{.Names}}"])
    if not names["available"] or names["returncode"] != 0:
        return {"available": False, "reason": names.get("reason", "docker_unavailable")}
    containers = []
    all_names = names["stdout"].splitlines()
    for name in all_names[:100]:
        if not name or any(ch in name for ch in "\r\n\x00"):
            continue
        inspected = fixed_command([
            "docker", "inspect", "--format",
            "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}|{{.Config.Image}}|{{index .Config.Labels \"com.docker.compose.project\"}}|{{index .Config.Labels \"com.docker.compose.service\"}}|{{.RestartCount}}|{{.State.ExitCode}}|{{range $n,$v := .NetworkSettings.Networks}}{{$n}},{{end}}|{{range $p,$b := .NetworkSettings.Ports}}{{$p}}={{range $b}}{{.HostIp}}:{{.HostPort}},{{end}};{{end}}",
            name,
        ])
        fields = inspected["stdout"].split("|", 8)
        networks = [x for x in fields[7].split(",") if x][:20] if len(fields) > 7 else []
        published = []
        if len(fields) > 8:
            for entry in fields[8].split(";")[:30]:
                if "=" in entry:
                    container_port, host_values = entry.split("=", 1)
                    for binding in host_values.split(",")[:5]:
                        if binding and ":" in binding:
                            host_ip, host_port = binding.rsplit(":", 1)
                            published.append({"container_port": container_port[:32],
                                              "host_ip": host_ip[:64], "host_port": host_port[:8]})
        containers.append({
            "name": name[:128],
            "state": fields[0][:32] if len(fields) > 0 else "unknown",
            "health": fields[1][:32] if len(fields) > 1 else "unknown",
            "image": fields[2][:160] if len(fields) > 2 else "unknown",
            "compose_project": fields[3][:96] if len(fields) > 3 and fields[3] != "<no value>" else None,
            "compose_service": fields[4][:96] if len(fields) > 4 and fields[4] != "<no value>" else None,
            "restart_count": int(fields[5]) if len(fields) > 5 and fields[5].isdigit() else None,
            "exit_code": int(fields[6]) if len(fields) > 6 and fields[6].lstrip("-").isdigit() else None,
            "networks": networks,
            "published_ports": published,
            "inspect_ok": inspected.get("returncode") == 0,
        })
    network_result = fixed_command(["docker", "network", "ls", "--format", "{{.Name}}|{{.Driver}}|{{.Scope}}"])
    networks = []
    if network_result.get("available") and network_result.get("returncode") == 0:
        for line in network_result["stdout"].splitlines()[:60]:
            fields = line.split("|", 2)
            if len(fields) == 3:
                networks.append({"name": fields[0][:128], "driver": fields[1][:32], "scope": fields[2][:32]})
    stats_result = fixed_command([
        "docker", "stats", "--no-stream", "--format",
        "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}",
    ], timeout=12)
    stats = []
    if stats_result.get("available") and stats_result.get("returncode") == 0:
        for line in stats_result["stdout"].splitlines()[:100]:
            fields = line.split("|", 3)
            if len(fields) == 4:
                stats.append({"name": fields[0][:128], "cpu_percent": fields[1][:24],
                              "memory_usage": fields[2][:64], "memory_percent": fields[3][:24]})
    return {
        "available": True, "containers": containers,
        "truncated": len(all_names) > 100,
        "networks": networks, "networks_truncated": len(network_result.get("stdout", "").splitlines()) > 60,
        "resource_usage": stats, "resource_usage_available": stats_result.get("returncode") == 0,
    }


def tcp_probe(port: int, host: str = "127.0.0.1") -> dict:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return {"reachable": True}
    except OSError:
        return {"reachable": False}


def collect() -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    try:
        load = list(os.getloadavg())
    except (AttributeError, OSError):
        load = []
    uptime = fixed_command(["uptime", "-p"])
    os_release = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith(("PRETTY_NAME=", "VERSION_ID=")):
                k, v = line.split("=", 1)
                os_release[k] = v.strip().strip('"')[:160]
    except OSError:
        pass
    return {
        "schema_version": 2,
        "collected_at": now.isoformat(),
        "agent": {"name": "aiops-debian-readonly", "version": "1.1.0"},
        "host": {"reported_name": os.environ.get("AIOPS_AGENT_HOST_LABEL", "SRV-DEB-05"),
                 "os": os_release, "kernel": platform.release()[:160],
                 "architecture": platform.machine()[:64], "uptime": uptime.get("stdout", "")[:256]},
        "resources": {"load_1_5_15": load, "memory_bytes": read_meminfo(),
                      "disk_root": disk_info("/"), "disk_home": disk_info("/home/aiops")},
        "docker": docker_inventory(),
        "runtime_contract": collect_runtime_contract(),
        "tcp_loopback": {str(p): tcp_probe(p) for p in (5432, 7233, 17777, 3000, 9090)},
    }


def github_request(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        GITHUB_API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json", "User-Agent": "AIOps2-Debian-Readonly-Agent"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise RuntimeError("GitHub API response exceeded size limit")
    return json.loads(raw or b"{}")


def publish(report: dict) -> None:
    if not TOKEN_PATH.is_file() or TOKEN_PATH.is_symlink():
        raise RuntimeError(f"GitHub token file missing or unsafe: {TOKEN_PATH}")
    mode = TOKEN_PATH.stat().st_mode & 0o777
    if mode & 0o077:
        raise RuntimeError("GitHub token file must have permissions 0600")
    token = TOKEN_PATH.read_text().strip()
    if not token or any(c.isspace() for c in token):
        raise RuntimeError("GitHub token file is empty or malformed")
    api_path = f"/repos/{REPOSITORY}/contents/{REPORT_PATH}"
    try:
        current = github_request("GET", api_path + "?ref=" + REPORT_BRANCH, token)
        sha = current.get("sha")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        sha = None
    content = json.dumps(report, indent=2, sort_keys=True).encode()
    if len(content) > MAX_REPORT_BYTES:
        raise RuntimeError("Report exceeds size limit")
    import base64
    body = {"message": "ops(debian): refresh read-only host report",
            "content": base64.b64encode(content).decode(),
            "branch": REPORT_BRANCH}
    if sha:
        body["sha"] = sha
    github_request("PUT", api_path, token, body)


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE_DIR, 0o700)
    with LOCK_PATH.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        report = collect()
        encoded = json.dumps(report, indent=2, sort_keys=True)
        if len(encoded.encode()) > MAX_REPORT_BYTES:
            raise RuntimeError("Report exceeds size limit")
        tmp = LATEST_PATH.with_suffix(".tmp")
        tmp.write_text(encoded + "\n")
        os.chmod(tmp, 0o600)
        tmp.replace(LATEST_PATH)
        # Cron collects every minute; publish one consolidated snapshot every 5 minutes.
        if dt.datetime.now(dt.timezone.utc).minute % 5 == 0 and TOKEN_PATH.is_file():
            publish(report)
            print("AIOPS_DEBIAN_REPORT=PUBLISHED")
        elif dt.datetime.now(dt.timezone.utc).minute % 5 == 0:
            print("AIOPS_DEBIAN_REPORT=COLLECTED_LOCAL_TOKEN_NOT_CONFIGURED")
        else:
            print("AIOPS_DEBIAN_REPORT=COLLECTED_LOCAL")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Error type only: never print request headers, token, or full exception context.
        print(f"AIOPS_DEBIAN_REPORT=FAILED error={type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
