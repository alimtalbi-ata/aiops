"""Validate resolved Compose JSON for the synthetic kit only."""
import json
import re
import sys
from pathlib import Path

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def validate_source(source):
    """Fail closed on profile declarations in the canonical, restricted YAML layout.

    Resolved Compose JSON drops profiles of inactive services, so check source first.
    Reject duplicate service headings and unsupported profile syntax rather than guess.
    """
    require(type(source) is str, "invalid compose source")
    blocks = re.findall(r"(?ms)^  (gamma|core|demo):[ \t]*\n(.*?)(?=^  [a-zA-Z][a-zA-Z0-9_-]*:|^networks:|\Z)", source)
    require(len(blocks) == 3 and {name for name, _ in blocks} == {"gamma", "core", "demo"}, "canonical service blocks")
    for name, block in blocks:
        declarations = re.findall(r"(?m)^    profiles:[ \t]*(.*?)\s*$", block)
        expected = ["[demo]"] if name == "demo" else []
        require(declarations == expected, "unsafe source profiles: " + name)
        require(not re.search(r"(?m)^\s+profiles\s*:", block.replace("    profiles: [demo]", "") if name == "demo" else block), "nested/duplicate profiles: " + name)

def validate(config):
    validate_source(Path(__file__).resolve().with_name("docker-compose.yml").read_text(encoding="utf-8"))
    services = config["services"]
    require(type(services) is dict and {"gamma", "core"} <= services.keys(), "missing mandatory service")
    require(set(services) <= {"gamma", "core", "demo"}, "unexpected service")
    require(set(config["networks"]) == {"edge", "backend"}, "unexpected networks")
    require(config["networks"]["backend"].get("internal") is True, "backend not internal")
    for net in config["networks"].values():
        require(type(net) is dict and set(net) <= {"name", "driver", "internal", "external"}, "unexpected network field")
        require(net.get("external", False) is False and net.get("driver", "bridge") == "bridge", "unsafe network")
    allowed = {"image","user","read_only","cap_drop","security_opt","ports","networks","volumes","environment","command","healthcheck","depends_on","profiles"}
    for name, s in services.items():
        require(type(s) is dict and set(s) <= allowed, "unexpected service field: " + name)
        require(type(s.get("image")) is str and re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", s["image"]), "unpinned image")
        require(s.get("user") == "65532:65532" and s.get("read_only") is True, "missing isolation")
        require(s.get("cap_drop") == ["ALL"], "cap_drop")
        require(s.get("security_opt") in (["no-new-privileges:true"], ["no-new-privileges=true"]), "security_opt")
        nets = s["networks"]
        require(type(nets) is dict and set(nets) == ({"edge","backend"} if name == "gamma" else {"backend"}), "network membership")
        require(all(v is None or v == {} for v in nets.values()), "network options")
        mounts = s["volumes"]
        require(type(mounts) is list and len(mounts) == 1, "mount count")
        m = mounts[0]
        require(type(m) is dict and m.get("type") == "bind" and m.get("target") == "/fixture.py" and m.get("read_only") is True, "mount mode")
        require(Path(m["source"]).resolve() == Path(__file__).resolve().with_name("fixture.py"), "mount source")
        require(set(m) <= {"type","source","target","read_only","bind"}, "mount options")
        require(set(m.get("bind", {})) <= {"create_host_path"}, "bind options")
        require(s.get("command") == ["python","/fixture.py"] and s.get("environment") == {"FIXTURE_ROLE":name}, "fixture command/environment")
        health = s.get("healthcheck")
        expected_health = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]
        require(type(health) is dict and health.get("test") == expected_health, "missing or unsafe healthcheck: " + name)
        require(health.get("disable") is not True and set(health) <= {"test", "interval", "timeout", "retries", "start_period", "start_interval"}, "unsafe healthcheck options: " + name)
        require(type(health.get("retries")) is int and 1 <= health["retries"] <= 12, "healthcheck retries: " + name)
        # docker compose config --format json normalizes durations to integer nanoseconds.
        # Keep health checks responsive; reject bools, strings and unbounded delays.
        for key, lower, upper in (
            ("interval", 1_000_000_000, 60_000_000_000),
            ("timeout", 1_000_000_000, 10_000_000_000),
            ("start_period", 0, 120_000_000_000),
            ("start_interval", 1_000_000_000, 60_000_000_000),
        ):
            if key in health:
                duration = health[key]
                require(type(duration) is int and lower <= duration <= upper, "healthcheck duration " + key + ": " + name)
        require("interval" in health and "timeout" in health, "healthcheck timing missing: " + name)
        require(health["timeout"] <= health["interval"], "healthcheck timeout exceeds interval: " + name)
        deps = s.get("depends_on", {})
        require(type(deps) is dict, "depends_on type: " + name)
        if name == "gamma":
            require(set(deps) == {"core"} and type(deps["core"]) is dict and deps["core"].get("condition") == "service_healthy", "gamma startup dependency")
        else:
            require(not deps, "unexpected startup dependency: " + name)
        ports = s.get("ports", [])
        require(type(ports) is list, "ports type")
        if name == "gamma":
            require(len(ports) == 1 and type(ports[0]) is dict, "gamma port count")
            p = ports[0]
            require(p.get("host_ip") == "127.0.0.1" and type(p.get("target")) is int and p["target"] == 8080 and p.get("published","0") in ("0",0) and p.get("protocol") == "tcp", "gamma port")
            require(set(p) <= {"host_ip","target","published","protocol","mode"} and p.get("mode","ingress") in ("ingress","host"), "port options")
        else:
            require(not ports, "unexpected published port")

if __name__ == "__main__":
    try:
        validate(json.load(sys.stdin))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        sys.exit("PREFLIGHT_FAIL: " + str(exc))
    print("PREFLIGHT_STATIC_PASS")
