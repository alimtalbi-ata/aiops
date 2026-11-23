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
    raw_compose = pathlib.Path(compose_path).read_text(encoding="utf-8")
    # Fail closed until a trusted, normalized Compose config is available.
    # Raw YAML must never be treated as resolved Compose configuration.
    if "${" in raw_compose or "$" in raw_compose:
        raise ValueError("unresolved Compose interpolation forbidden")
    document = yaml.safe_load(raw_compose)
    if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
        raise ValueError("invalid Compose services")
    # No transitive Compose imports are allowed in the single-file kit.
    # Validate before comparing service names: extends can inject host capabilities.
    if "include" in document:
        raise ValueError("Compose include forbidden")
    # Reject transitive host binds through named-volume driver options.
    definitions = document.get("volumes", {})
    if not isinstance(definitions, dict):
        raise ValueError("invalid top-level volumes")
    for volume_name, definition in definitions.items():
        if not isinstance(volume_name, str) or not volume_name:
            raise ValueError("invalid named volume")
        if definition is None:
            continue
        if not isinstance(definition, dict) or definition:
            raise ValueError("untrusted named volume driver/opts/external forbidden: " + volume_name)
    actual = document["services"]
    if any(not isinstance(spec, dict) or "extends" in spec for spec in actual.values()):
        raise ValueError("Compose extends forbidden")
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
        if any(isinstance(spec.get(k), str) and (spec[k] == "host" or spec[k].startswith(("container:", "service:"))) for k in ("network_mode", "pid", "ipc", "userns_mode", "cgroup", "uts")):
            raise ValueError("host namespace forbidden: " + name)
        # volumes_from inherits mounts from services or external containers; no transitive mounts.
        if "volumes_from" in spec:
            raise ValueError("volumes_from forbidden: " + name)
        if spec.get("devices") or spec.get("cap_add") or spec.get("security_opt"):
            raise ValueError("host capability forbidden: " + name)
        if spec.get("volumes"):
            # Named volumes only; bind mounts require separate security review.
            for volume in spec["volumes"]:
                if isinstance(volume, str):
                    source = volume.split(":", 1)[0]
                    if not source or source.startswith(("/", ".", "~")) or "/" in source or "\\" in source:
                        raise ValueError("host bind mount forbidden: " + name)
                    if source not in definitions:
                        raise ValueError("undeclared short-form volume source: " + name)
                elif isinstance(volume, dict):
                    if volume.get("type") != "volume":
                        raise ValueError("host bind mount forbidden: " + name)
                    source = volume.get("source")
                    # Long-form volume mounts must use a simple, declared local volume name.
                    # Reject absolute/relative host paths and unknown named volumes.
                    if not isinstance(source, str) or not source or not source.replace("_", "a").replace("-", "a").replace(".", "a").isalnum() or source.startswith("."):
                        raise ValueError("untrusted long-form volume source: " + name)
                    if source not in definitions:
                        raise ValueError("undeclared long-form volume source: " + name)
                else:
                    raise ValueError("invalid volume: " + name)
        for port in spec.get("ports", []):
            if isinstance(port, int):
                published = port
            elif isinstance(port, str):
                value = port.split("/") [0].rsplit(":", 1)[0]
                if not value.isdigit() and ":" in port:
                    raise ValueError("unresolved published port forbidden: " + name)
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
