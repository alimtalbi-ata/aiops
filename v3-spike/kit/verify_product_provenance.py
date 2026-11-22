"""Structural OCI provenance check; no registry lookup or independent attestation."""
import json
import pathlib
import re
import sys

from product_preflight import validate

def verify(bom_path, provenance_path):
    bom = json.loads(pathlib.Path(bom_path).read_text(encoding="utf-8"))
    validate(bom)
    provenance = json.loads(pathlib.Path(provenance_path).read_text(encoding="utf-8"))
    if not isinstance(provenance, dict) or provenance.get("independently_verified") is not True:
        raise ValueError("independent OCI provenance verification missing")
    records = provenance.get("images")
    if not isinstance(records, dict) or set(records) != set(bom["services"]):
        raise ValueError("provenance service set mismatch")
    for service, entry in bom["services"].items():
        image = entry["image"]
        record = records[service]
        if not isinstance(record, dict) or record.get("image") != image:
            raise ValueError("BOM provenance mismatch: " + service)
        if not re.search(r"@sha256:[a-f0-9]{64}$", image):
            raise ValueError("image digest missing: " + service)
        if any(not isinstance(record.get(k), str) or not record[k].strip()
               for k in ("license", "source", "registry_receipt")):
            raise ValueError("license/source/registry receipt missing: " + service)
    return True

if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("expected BOM and provenance paths")
        verify(*sys.argv[1:])
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("STATIC_FAIL:", exc, file=sys.stderr)
        sys.exit(2)
    print("STATIC_PASS provenance manifest structure; registry receipts NOT independently verified")
