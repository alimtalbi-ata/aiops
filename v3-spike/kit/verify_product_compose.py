"""Fail-closed BOM/Compose consistency gate, no runtime claims."""
import json
import pathlib
import re
import sys

def verify(bom_path, compose_path):
    bom = json.loads(pathlib.Path(bom_path).read_text(encoding="utf-8"))
    compose = pathlib.Path(compose_path).read_text(encoding="utf-8")
    if not compose.strip():
        raise ValueError("empty Compose")
    images = bom.get("images", {})
    if not isinstance(images, dict) or not images:
        raise ValueError("BOM images missing")
    for service, image in images.items():
        if not re.search(r"(?m)^  " + re.escape(service) + r":\\s*$", compose):
            raise ValueError("service missing: " + service)
        if image not in compose:
            raise ValueError("image mismatch: " + service)
    return True

if __name__ == "__main__":
    try:
        verify(*sys.argv[1:])
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(2)
    print("STATIC_PASS BOM/Compose text check; docker compose config required")
