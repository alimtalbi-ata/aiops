"""Fail-closed BOM/Compose consistency and dangerous-host-capability policy; static only."""
import json
import pathlib
import sys
from product_preflight import validate

PROTECTED_PORTS = {7770, 7777, 7790}
DRAFT_VOLUMES = {"core": ("core_data", "/var/lib/aiops"),
                 "temporal": ("temporal_data", "/var/lib/temporal"),
                 "evidence": ("evidence_data", "/var/lib/evidence")}

def verify_draft_volumes(document, normalized=False):
    """Exact draft topology; logical keys and their own effective aliases only."""
    if document.get("name") != "aiops-v3":
        raise ValueError("unexpected draft project name")
    definitions = document.get("volumes", {})
    if not isinstance(definitions, dict) or set(definitions) != {v[0] for v in DRAFT_VOLUMES.values()}:
        raise ValueError("draft volume declarations mismatch")
    for key, spec in definitions.items():
        if normalized:
            if (not isinstance(spec, dict) or set(spec) - {"name", "driver"}
                    or spec.get("name") != "aiops-v3_" + key or spec.get("driver", "local") != "local"):
                raise ValueError("untrusted draft effective volume: " + key)
        elif spec not in ({}, None):
            raise ValueError("untrusted draft raw volume: " + key)
    services = document["services"]
    if not set(DRAFT_VOLUMES).issubset(services):
        raise ValueError("draft volume owner missing")
    for name, spec in services.items():
        mounts = spec.get("volumes", [])
        expected = DRAFT_VOLUMES.get(name)
        if not isinstance(mounts, list) or len(mounts) != int(expected is not None):
            raise ValueError("draft volume cardinality: " + name)
        if expected is None:
            continue
        key, target = expected
        mount = mounts[0]
        if isinstance(mount, str) and not normalized:
            if mount != key + ":" + target:
                raise ValueError("draft raw volume mapping: " + name)
        elif isinstance(mount, dict):
            allowed = {key, "aiops-v3_" + key} if normalized else {key}
            if (set(mount) - {"type", "source", "target", "volume"}
                    or mount.get("type") != "volume" or mount.get("source") not in allowed
                    or mount.get("target") != target or mount.get("volume", {}) != {}):
                raise ValueError("draft volume mapping: " + name)
        else:
            raise ValueError("draft volume mapping: " + name)

def verify(bom_path, compose_path, normalized_path=None):
    import yaml
    bom = json.loads(pathlib.Path(bom_path).read_text(encoding="utf-8"))
    validate(bom)
    raw_compose = pathlib.Path(compose_path).read_text(encoding="utf-8")
    # Raw interpolation is allowed ONLY for image inputs when a separately
    # normalized Compose JSON is supplied; never trust raw YAML as effective config.
    document = yaml.safe_load(raw_compose)
    draft = document.get("name") == "aiops-v3" or pathlib.Path(compose_path).parent.name == "product"
    if draft:
        verify_draft_volumes(document)
    if normalized_path is None and "$" in raw_compose:
        raise ValueError("unresolved Compose interpolation forbidden")
    if normalized_path is not None:
        def check_interpolation(value, key=""):
            if isinstance(value, dict):
                for k, v in value.items():
                    check_interpolation(v, k)
            elif isinstance(value, list):
                for v in value:
                    check_interpolation(v, key)
            elif isinstance(value, str) and "$" in value:
                if key != "image" or not (
                    __import__("re").fullmatch(r"\$\{[A-Z][A-Z0-9_]*_IMAGE:\?[^}]+\}", value)
                    or __import__("re").fullmatch(r"\$\{DEMO_IMAGE:-registry\.invalid/disabled-demo@sha256:0{64}\}", value)
                ):
                    raise ValueError("unsafe Compose interpolation forbidden")
        check_interpolation(document)
        effective = json.loads(pathlib.Path(normalized_path).read_text(encoding="utf-8"))
        if not isinstance(effective, dict) or not isinstance(effective.get("services"), dict):
            raise ValueError("invalid normalized Compose services")
        # Compose omits inactive profiles from normalized default config.
        # Validate the raw topology against the full BOM before selecting a profile.
        raw_services = document.get("services")
        if not isinstance(raw_services, dict) or set(raw_services) != set(bom["services"]):
            raise ValueError("raw BOM/Compose service set mismatch")
        for name, entry in bom["services"].items():
            spec = raw_services[name]
            if not isinstance(spec, dict):
                raise ValueError("invalid raw service: " + name)
            declared = spec.get("profiles", [])
            if entry["profile"] == "default":
                if declared:
                    raise ValueError("required service hidden behind profile: " + name)
            elif declared != [entry["profile"]]:
                raise ValueError("raw profile mismatch: " + name)
        if draft:
            verify_draft_volumes(effective, normalized=True)
        selected = set(effective["services"])
        required = {name for name, entry in bom["services"].items()
                    if entry["profile"] == "default"}
        if not required.issubset(selected) or not selected.issubset(set(raw_services)):
            raise ValueError("normalized Compose service set mismatch")
        active_profiles = {bom["services"][name]["profile"] for name in selected
                           if bom["services"][name]["profile"] != "default"}
        expected_selected = required | {name for name, entry in bom["services"].items()
                                         if entry["profile"] in active_profiles}
        if selected != expected_selected:
            raise ValueError("normalized Compose partial profile service set mismatch")
        # The raw full topology remains authoritative for inactive services; normalized
        # effective services are checked for selected profiles only.
        document = {**document, "services": effective["services"]}
        bom = {**bom, "services": {name: bom["services"][name] for name in selected}}
    if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
        raise ValueError("invalid Compose services")
    # No transitive Compose imports are allowed in the single-file kit.
    # Validate before comparing service names: extends can inject host capabilities.
    if "include" in document:
        raise ValueError("Compose include forbidden")
    # Validate original definitions before normalized name translation. A normalized
    # service set must never erase raw driver_opts/external provenance.
    raw_definitions = document.get("volumes", {})
    if not isinstance(raw_definitions, dict):
        raise ValueError("invalid raw top-level volumes")
    for volume_name, definition in raw_definitions.items():
        if not isinstance(volume_name, str) or not volume_name:
            raise ValueError("invalid named volume")
        if definition is not None and (not isinstance(definition, dict) or definition):
            raise ValueError("untrusted named volume driver/opts/external forbidden: " + volume_name)
    definitions = raw_definitions
    # Normalized Compose mounts use effective project-prefixed volume names.
    # Retain the raw topology policy, but compare effective mounts to effective
    # declarations; never allow arbitrary external or bind sources.
    if normalized_path is not None:
        effective_volumes = effective.get("volumes", {})
        if not isinstance(effective_volumes, dict):
            raise ValueError("invalid normalized volumes")
        raw_volumes = yaml.safe_load(raw_compose).get("volumes", {})
        if not isinstance(raw_volumes, dict) or set(effective_volumes) != set(raw_volumes):
            raise ValueError("normalized volume declarations mismatch")
        for key, spec in effective_volumes.items():
            if not isinstance(spec, dict) or not isinstance(spec.get("name"), str) or not spec["name"]:
                raise ValueError("invalid effective volume name: " + key)
        for key, spec in effective_volumes.items():
            # Compose may add its default driver: local. Any options, external
            # provenance or alternate driver must fail closed.
            if set(spec) - {"name", "driver"} or spec.get("driver", "local") != "local":
                raise ValueError("untrusted normalized named volume driver/opts/external forbidden: " + key)
        aliases = {spec["name"]: {} for spec in effective_volumes.values()}
        if len(aliases) != len(effective_volumes):
            raise ValueError("duplicate effective volume names")
        definitions = {**raw_volumes, **aliases}
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
        if spec.get("devices") or spec.get("cap_add"):
            raise ValueError("host capability forbidden: " + name)
        security = spec.get("security_opt", [])
        if security not in ([], ["no-new-privileges:true"], ["no-new-privileges=true"]):
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
                published = None
            elif isinstance(port, str):
                value = port.split("/")[0].rsplit(":", 1)[0] if ":" in port else ""
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
        if len(sys.argv) not in (3, 4):
            raise ValueError("expected BOM, canonical Compose, optional normalized JSON")
        verify(*sys.argv[1:])
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("STATIC_FAIL:", exc, file=sys.stderr)
        sys.exit(2)
    print("STATIC_PASS BOM/Compose static policy; runtime NOT_ATTESTED")
