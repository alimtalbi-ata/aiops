"""Fail-closed BOM/Compose consistency and dangerous-host-capability policy; static only."""
import json
import pathlib
import sys
from product_preflight import validate

PROTECTED_PORTS = {7770, 7777, 7790}
def verify(bom_path, compose_path):
    import yaml
    bom = json.loads(pathlib.Path(bom_path).read_text(encoding="utf-8"))
    validate(bom)
    document = yaml.safe_load(pathlib.Path(compose_path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
        raise ValueError("invalid Compose services")
    actual = document["services"]
    expected = bom["services"]
    if set(actual) != set(expected):
        raise ValueError("BOM/Compose service set mismatch")
    for name, entry in expected.items():
        spec = actual[name]
        if not isinstance(spec, dict) or spec.get("image") != entry["image"]:
            raise ValueError("image mismatch: " + name)
        profiles = spec.get("profiles", [])
        if entry["profile"] == "default":
            if profiles:
                raise ValueError("required service hidden behind profile: " + name)
        elif profiles != [entry["profile"]]:
            raise ValueError("profile mismatch: " + name)
        if spec.get("privileged") is not None and spec["privileged"] is not False:
            raise ValueError("privileged forbidden: " + name)
        if spec.get("network_mode") in ("host", "service:host") or spec.get("pid") == "host" or spec.get("ipc") == "host":
            raise ValueError("host namespace forbidden: " + name)
        if spec.get("devices") or spec.get("cap_add") or spec.get("security_opt"):
            raise ValueError("host capability forbidden: " + name)
        if spec.get("volumes"):
            # Named volumes only; bind mounts require separate security review.
            for volume in spec["volumes"]:
                if isinstance(volume, str):
                    source = volume.split(":", 1)[0]
                    if source.startswith(("/", ".", "~")):
                        raise ValueError("host bind mount forbidden: " + name)
                elif isinstance(volume, dict):
                    if volume.get("type") != "volume":
                        raise ValueError("host bind mount forbidden: " + name)
                else:
                    raise ValueError("invalid volume: " + name)
        for port in spec.get("ports", []):
            if isinstance(port, int):
                published = port
            elif isinstance(port, str):
                value = port.split("/") [0].rsplit(":", 1)[0]
                published = int(value) if value.isdigit() else None
            elif isinstance(port, dict):
                published = port.get("published")
            else:
                raise ValueError("invalid port declaration: " + name)
            if published is not None and int(published) in PROTECTED_PORTS:
                raise ValueError("protected port forbidden: " + name)
    return True

if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("expected BOM and canonical Compose paths")
        verify(*sys.argv[1:])
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("STATIC_FAIL:", exc, file=sys.stderr)
        sys.exit(2)
    print("STATIC_PASS BOM/Compose static policy; runtime NOT_ATTESTED")
