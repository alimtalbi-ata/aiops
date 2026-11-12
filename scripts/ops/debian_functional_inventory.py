#!/usr/bin/env python3
"""AIOps2 Debian exhaustive discovery + bounded functional probes (read-only).

Run manually on Debian. Never prints env, secrets, logs, full unit files, or
database contents. No Docker exec, HTTP POST, restart, cron or deployment.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_ITEMS = 400
TIMEOUT = 12
SAFE_PORTS = (7777, 17777, 9090, 3000, 8000, 8001, 8002, 8080, 8081, 5432, 6379, 7233)
HEALTH_PATHS = ("/health", "/healthz", "/ready", "/readyz")
REDACT = re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key|credential|authorization|private[_-]?key)")


def command(*args, timeout=TIMEOUT):
    if not shutil.which(args[0]):
        return {"status": "missing_command"}
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=timeout,
                           check=False, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                                             "LANG": "C", "LC_ALL": "C"})
        return {"status": "ok" if p.returncode == 0 else "failed",
                "returncode": p.returncode, "stdout": p.stdout[:100000]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    except OSError as exc:
        return {"status": "error", "type": type(exc).__name__}


def lines(*args):
    result = command(*args)
    return {"status": result["status"],
            "items": [s for s in result.get("stdout", "").splitlines() if s][:MAX_ITEMS]}


def probe(port, path):
    url = "http://127.0.0.1:%d%s" % (port, path)
    try:
        request = urllib.request.Request(url, method="GET",
                                         headers={"User-Agent": "aiops2-readonly-audit/1"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=2) as response:
            # Do not collect response bodies: may contain confidential data.
            return {"status": "responded", "http_status": response.status}
    except urllib.error.HTTPError as exc:
        return {"status": "responded", "http_status": exc.code}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"status": "unreachable"}


def collect(probe_http=False):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report = {
        "schema": "aiops2-debian-functional-inventory-v1",
        "captured_at_utc": now,
        "scope": "manual_read_only_host_inventory_and_optional_loopback_http_probes",
        "limitations": [
            "No credentialed GLPI/DB/Temporal API workflow is performed.",
            "HTTP response is reachability, not business functionality.",
            "No source-to-image provenance, backup or restore proof.",
            "Unit names, image tags, container names and listening ports can be sensitive: review locally.",
            "No historical 48h chronology can be inferred from one snapshot.",
        ],
        "clock": {},
        "docker": {},
        "systemd": {},
        "cron": {},
        "storage": {},
        "network": {},
        "functional": {},
    }
    report["clock"]["timedatectl"] = lines("timedatectl", "show",
        "--property=Timezone", "--property=NTPSynchronized",
        "--property=NTP", "--property=LocalRTC",
        "--property=TimeUSec", "--property=RTCTimeUSec")
    report["clock"]["chrony_tracking"] = lines("chronyc", "tracking")
    report["clock"]["ntp_peers"] = lines("timedatectl", "timesync-status")
    report["clock"]["utc"] = now
    report["docker"]["version"] = lines("docker", "version", "--format",
                                        "{{.Server.Version}}")
    report["docker"]["containers"] = lines("docker", "ps", "-a",
        "--format", "{{.Names}}|{{.Image}}|{{.Status}}")
    report["docker"]["images"] = lines("docker", "images", "--no-trunc",
        "--format", "{{.Repository}}:{{.Tag}}|{{.ID}}")
    report["docker"]["volumes"] = lines("docker", "volume", "ls", "--format", "{{.Name}}")
    report["docker"]["networks"] = lines("docker", "network", "ls",
        "--format", "{{.Name}}|{{.Driver}}")
    report["docker"]["compose_projects"] = lines("docker", "compose", "ls", "-a",
        "--format", "json")
    report["systemd"]["running_services"] = lines("systemctl", "list-units",
        "--type=service", "--state=running", "--no-legend", "--plain")
    report["systemd"]["failed_services"] = lines("systemctl", "--failed",
        "--type=service", "--no-legend", "--plain")
    report["systemd"]["timers"] = lines("systemctl", "list-timers",
        "--all", "--no-legend", "--plain")
    # List only cron filenames; never read crontab commands or files.
    cron_dirs = ("/etc/cron.d", "/etc/cron.hourly", "/etc/cron.daily",
                 "/etc/cron.weekly", "/etc/cron.monthly")
    for directory in cron_dirs:
        p = Path(directory)
        try:
            report["cron"][directory] = sorted(x.name for x in p.iterdir()
                if not REDACT.search(x.name))[:MAX_ITEMS]
        except OSError:
            report["cron"][directory] = "unavailable"
    report["cron"]["user_crontab_presence"] = command("crontab", "-l")["status"]
    report["storage"]["mount_points"] = lines("findmnt", "-rn",
        "-o", "TARGET,FSTYPE,OPTIONS")
    report["storage"]["disk_usage"] = lines("df", "-hP")
    report["storage"]["block_devices"] = lines("lsblk", "-o",
        "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT", "-n")
    report["network"]["listening_tcp"] = lines("ss", "-lntH")
    report["functional"]["http_probe_enabled"] = probe_http
    if probe_http:
        report["functional"]["loopback_http"] = {
            str(port): {path: probe(port, path) for path in HEALTH_PATHS}
            for port in SAFE_PORTS
        }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True,
                        help="new private local JSON path (will not overwrite)")
    parser.add_argument("--probe-http", action="store_true",
                        help="opt in to bounded GET health probes on 127.0.0.1 only")
    args = parser.parse_args()
    result = collect(args.probe_http)
    path = Path(args.output)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)
        file.write("\n")
    print("audit_created=" + str(path))
    print("captured_at_utc=" + result["captured_at_utc"])
    print("docker_containers_seen=" + str(len(result["docker"]["containers"]["items"])))
    print("review_file_locally_before_sharing=yes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
