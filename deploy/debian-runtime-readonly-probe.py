#!/usr/bin/env python3
"""Read-only SRV-DEB-05 runtime contract for the EXISTING reporter cron.

Prints a redacted JSON fragment to stdout. Never deploys, writes Docker,
reads .env, opens SSH, or publishes a second report. Installation/wiring
to the existing cron is a separate, operator-approved step.
"""
import datetime as dt
import json
import os
import re
import socket
import subprocess
import urllib.request

PORTS = ("7777", "17777", "17778")
IMAGE_ID = re.compile(r"sha256:[a-f0-9]{64}\Z")
COMMIT = re.compile(r"[a-f0-9]{40}\Z")
DIGEST = re.compile(r"@sha256:([a-f0-9]{64})\Z")
PORTAL = "aiops2-rebuild-portal"
CANDIDATE = "aiops2-portal-candidate-web-20261029"


def safe_run(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                check=False, timeout=8)
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def inspect(name, runner):
    raw = runner(["docker", "inspect", "--format", "{{json .}}", name])
    if raw is None:
        return {"observed": False, "status": "UNKNOWN"}
    try:
        obj = json.loads(raw)
        state = obj.get("State") or {}
        config = obj.get("Config") or {}
        host = obj.get("HostConfig") or {}
        network = obj.get("NetworkSettings") or {}
        image_id = obj.get("Image")
        if not isinstance(image_id, str) or not IMAGE_ID.fullmatch(image_id):
            image_id = None
        binds = []
        for internal, entries in (host.get("PortBindings") or {}).items():
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                port = str(entry.get("HostPort", ""))
                if port in PORTS:
                    binds.append({
                        "container_port": str(internal),
                        "host_port": int(port),
                        "host_ip": str(entry.get("HostIp", "")),
                    })
        digests = []
        if image_id:
            raw_image = runner(["docker", "image", "inspect", "--format",
                                "{{json .RepoDigests}}", image_id])
            if raw_image is not None:
                for value in json.loads(raw_image) or []:
                    match = DIGEST.search(value) if isinstance(value, str) else None
                    if match:
                        digests.append("sha256:" + match.group(1))
        labels = config.get("Labels") or {}
        mounts = obj.get("Mounts") or []
        networks = network.get("Networks") or {}
        return {
            "observed": True,
            "state": str(state.get("Status", "UNKNOWN")),
            "health": str((state.get("Health") or {}).get("Status", "UNKNOWN")),
            "compose_project": str(labels.get("com.docker.compose.project", "UNKNOWN")),
            "image_id_sha256": image_id,
            "registry_manifest_digests": sorted(set(digests)),
            "bindings": sorted(binds, key=lambda b: (b["host_port"], b["container_port"])),
            "mount_count": len(mounts),
            "network_count": len(networks),
        }
    except (ValueError, TypeError, AttributeError, KeyError):
        return {"observed": False, "status": "UNKNOWN"}


def http_7777():
    url = "http://127.0.0.1:7777/health"
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=5) as response:
            if response.status != 200:
                return {"http_status": response.status, "qualified": False}
            raw = response.read(8193)
        if len(raw) > 8192:
            return {"http_status": 200, "qualified": False}
        body = json.loads(raw)
        return {
            "http_status": 200,
            "qualified": (body.get("status") == "ok"
                          and body.get("component") == "portal"
                          and body.get("external_port") == 7777),
            "status": str(body.get("status", "UNKNOWN")),
            "component": str(body.get("component", "UNKNOWN")),
            "external_port": body.get("external_port")
            if type(body.get("external_port")) is int else None,
        }
    except (OSError, ValueError, TypeError):
        return {"http_status": None, "qualified": False}


def tcp_loopback(port):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=1):
            return True
    except OSError:
        return False


def collect(runner=safe_run, http_probe=http_7777,
            tcp_probe=tcp_loopback, clock=None):
    now = clock() if clock else dt.datetime.now(dt.timezone.utc)
    checkout = os.environ.get("AIOPS_DEV_CHECKOUT", "")
    sha = None
    if checkout:
        raw = runner(["git", "-C", checkout, "rev-parse", "HEAD"])
        value = raw.strip() if isinstance(raw, str) else ""
        if COMMIT.fullmatch(value):
            sha = value
    return {
        "schema": "aiops.debian-runtime-contract.v2",
        "collected_at": now.astimezone(dt.timezone.utc).isoformat(),
        "source": "EXISTING_HOST_READ_ONLY_PROBE",
        "cron_wiring_attested": False,
        "checkout_sha": sha,
        "portal": inspect(PORTAL, runner),
        "candidate_portal": inspect(CANDIDATE, runner),
        "tcp_loopback": {port: bool(tcp_probe(port)) for port in PORTS},
        "http_7777": http_probe(),
        "external_tls_sso_glpi_e2e_verified": False,
        "single_portal_verified": False,
        "deployed_candidate_sha_verified": False,
        "release_stable": "NO_GO",
    }


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True, separators=(",", ":")))
