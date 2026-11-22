"""Fail-closed canonical BOM/Compose consistency, static only."""
import json
import pathlib
import sys

from product_preflight import validate

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
    return True

if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("expected BOM and canonical Compose paths")
        verify(*sys.argv[1:])
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("STATIC_FAIL:", exc, file=sys.stderr)
        sys.exit(2)
    print("STATIC_PASS BOM/Compose structural check; runtime NOT_ATTESTED")
