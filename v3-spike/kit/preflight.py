"""Validate resolved Compose JSON from stdin; fail closed. No Docker mutation."""
import json
import re
import sys

def validate(config):
    services = config["services"]
    if not {"gamma", "core"} <= services.keys():
        raise ValueError("missing mandatory service")
    if set(services) - {"gamma", "core", "demo"}:
        raise ValueError("unexpected service")
    for name, service in services.items():
        if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", service.get("image", "")):
            raise ValueError("unpinned image: " + name)
        if service.get("privileged") or service.get("network_mode") or service.get("build"):
            raise ValueError("unsafe service: " + name)
        if service.get("user") != "65532:65532" or not service.get("read_only"):
            raise ValueError("missing isolation: " + name)
        ports = service.get("ports", [])
        if name == "gamma":
            if len(ports) != 1 or ports[0].get("host_ip") != "127.0.0.1" or ports[0].get("target") != 8080 or str(ports[0].get("published", "0")) != "0":
                raise ValueError("gamma port not ephemeral loopback")
        elif ports:
            raise ValueError("unexpected published port: " + name)
    if not config["networks"]["backend"].get("internal"):
        raise ValueError("backend not internal")

if __name__ == "__main__":
    try:
        validate(json.load(sys.stdin))
    except (ValueError, KeyError, TypeError) as exc:
        sys.exit("PREFLIGHT_FAIL: " + str(exc))
    print("PREFLIGHT_STATIC_PASS")
