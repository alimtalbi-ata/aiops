"""Bounded read-only existing Debian portal probe; never serialize raw Docker inspect."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import urllib.error
import urllib.request

PORTS = (7777, 17777, 17778)
PORTAL = "aiops2-rebuild-portal"
CANDIDATE = "aiops2-portal-candidate-web-20261029"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
NAME = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")
PORT = re.compile(r"^[0-9]{1,5}/(tcp|udp)$")


def _run(argv, timeout=5):
    """Fixed argv only; discard stderr and never serialize raw stdout."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           check=False)
        if p.returncode == 0 and len(p.stdout) <= 131072:
            return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _ports(mapping):
    result = []
    if not isinstance(mapping, dict):
        return result
    for container_port, bindings in sorted(mapping.items())[:24]:
        if not isinstance(container_port, str) or not PORT.fullmatch(container_port):
            continue
        if not isinstance(bindings, list):
            continue
        for item in bindings[:4]:
            if not isinstance(item, dict):
                continue
            host_port, host_ip = item.get("HostPort"), item.get("HostIp")
            if (not isinstance(host_port, str) or not host_port.isdigit()
                    or not 1 <= int(host_port) <= 65535
                    or not isinstance(host_ip, str)
                    or not re.fullmatch(r"[0-9a-fA-F:.]{1,64}", host_ip)):
                continue
            result.append({"container_port": container_port,
                           "host_ip": host_ip, "host_port": int(host_port)})
    return result


def _container(name):
    """Whitelisted fields only; Config.Env and bind paths are never exported."""
    raw = _run(["docker", "inspect", "--type", "container", name])
    if raw is None:
        return {"inspection": "UNKNOWN"}
    try:
        objects = json.loads(raw)
        if not isinstance(objects, list) or len(objects) != 1:
            return {"inspection": "UNKNOWN"}
        obj = objects[0]
        config, host, net, state = (obj.get("Config") or {},
                                    obj.get("HostConfig") or {},
                                    obj.get("NetworkSettings") or {},
                                    obj.get("State") or {})
        labels = config.get("Labels") or {}
        mounts = obj.get("Mounts") or []
        named = sorted({m["Name"] for m in mounts
                        if isinstance(m, dict) and m.get("Type") == "volume"
                        and isinstance(m.get("Name"), str)
                        and NAME.fullmatch(m["Name"])})[:16]
        networks = sorted(k for k in (net.get("Networks") or {})
                          if isinstance(k, str) and NAME.fullmatch(k))[:16]
        image_id = obj.get("Image")
        revision = labels.get("org.opencontainers.image.revision")
        health = (state.get("Health") or {}).get("Status")
        return {
            "inspection": "READ_ONLY",
            "state": state.get("Status") if state.get("Status") in
                     ("running", "exited", "created", "paused", "restarting") else "unknown",
            "health": health if health in ("healthy", "unhealthy", "starting") else "unknown",
            "compose_project": labels.get("com.docker.compose.project")
                               if labels.get("com.docker.compose.project") in
                               ("aiops2-rebuild", "aiops2") else "UNKNOWN",
            "compose_service": labels.get("com.docker.compose.service")
                               if isinstance(labels.get("com.docker.compose.service"), str)
                               and NAME.fullmatch(labels["com.docker.compose.service"])
                               else None,
            "image_id_sha256": image_id if isinstance(image_id, str)
                               and DIGEST.fullmatch(image_id) else None,
            "image_revision": revision if isinstance(revision, str)
                              and SHA.fullmatch(revision) else None,
            "configured_port_bindings": _ports(host.get("PortBindings")),
            "observed_published_ports": _ports(net.get("Ports")),
            "network_names": networks,
            "named_volume_names": named,
            "bind_mount_count": sum(1 for m in mounts if isinstance(m, dict)
                                    and m.get("Type") == "bind"),
            "volume_count": sum(1 for m in mounts if isinstance(m, dict)
                                and m.get("Type") == "volume"),
        }
    except (TypeError, ValueError, KeyError, AttributeError):
        return {"inspection": "UNKNOWN"}


def _tcp(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return {"reachable": True}
    except OSError:
        return {"reachable": False}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_7777():
    """No redirects, response echo, remote URL or browser bearer."""
    try:
        opener = urllib.request.build_opener(_NoRedirect)
        request = urllib.request.Request("http://127.0.0.1:7777/health",
                                         headers={"Accept": "application/json"})
        with opener.open(request, timeout=3) as response:
            if response.status != 200:
                return {"http_200_json_ok": False}
            raw = response.read(4097)
        if len(raw) > 4096:
            return {"http_200_json_ok": False}
        body = json.loads(raw)
        return {"http_200_json_ok": (isinstance(body, dict)
                and body.get("status") == "ok"
                and body.get("component") == "portal"
                and type(body.get("external_port")) is int
                and body["external_port"] == 7777)}
    except (OSError, ValueError, urllib.error.URLError):
        return {"http_200_json_ok": False}


def _sha_file(path):
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _checkout():
    root = os.environ.get("AIOPS_DEV_CHECKOUT",
                          "/home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e")
    head = _run(["git", "-C", root, "rev-parse", "--verify", "HEAD"])
    applied = Path("/home/aiops/aiops2-auto-deploy/applied.sha")
    try:
        applied_head = applied.read_text().strip() if not applied.is_symlink() else None
    except OSError:
        applied_head = None
    return {"source_checkout_head": head if head and SHA.fullmatch(head) else None,
            "stable_poller_applied_sha": applied_head
            if applied_head and SHA.fullmatch(applied_head) else None}


def collect_runtime_contract():
    portal = _container(PORTAL)
    candidate = _container(CANDIDATE)
    bindings = portal.get("observed_published_ports", [])
    local = _http_7777()
    valid = (portal.get("inspection") == "READ_ONLY"
             and portal.get("compose_project") == "aiops2-rebuild"
             and portal.get("state") == "running"
             and portal.get("health") == "healthy"
             and any(p["host_port"] == 7777 and p["container_port"] == "777/tcp"
                     for p in bindings)
             and local["http_200_json_ok"])
    return {
        "schema": "aiops.debian-portal-readonly-contract.v1",
        "portal": portal, "candidate": candidate,
        "tcp_loopback": {str(p): _tcp(p) for p in PORTS},
        "portal_http_7777": local,
        "local_7777": "VERIFIED_BY_HOST_PROBE" if valid else "NOT_VERIFIED",
        "external_access": "NOT_TESTED", "native_glpi_sso_e2e": "NOT_TESTED",
        "unique_public_entrypoint": "NOT_VERIFIED",
        "source": _checkout(),
        "installed_reporter_sha256": _sha_file(
            Path.home() / ".local/bin/aiops-debian-reporter"),
        "probe_sha256": _sha_file(Path(__file__)),
        "deployed_candidate_sha": None,
        "deployment_action": "NONE",
    }
