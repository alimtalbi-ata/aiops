"""Fail-closed structural provenance gate; does not independently attest registry existence."""
import json
import re
import sys

def verify(bom_path, provenance_path):
    bom = json.load(open(bom_path, encoding="utf-8"))
    provenance = json.load(open(provenance_path, encoding="utf-8"))
    if not isinstance(provenance, dict) or provenance.get("independently_verified") is not True:
        raise ValueError("independent OCI provenance verification missing")
    records = provenance.get("images")
    if not isinstance(records, dict) or not records:
        raise ValueError("image provenance records missing")
    images = bom.get("images", {})
    if not isinstance(images, dict) or not images:
        raise ValueError("BOM images missing")
    for service, image in images.items():
        record = records.get(service)
        if not isinstance(record, dict) or record.get("image") != image:
            raise ValueError("BOM provenance mismatch: " + service)
        if not re.search(r"@sha256:[a-f0-9]{64}$", image):
            raise ValueError("image digest missing: " + service)
        if not record.get("license") or not record.get("source") or not record.get("registry_receipt"):
            raise ValueError("license/source/registry receipt missing: " + service)
    return True

if __name__ == "__main__":
    try:
        verify(*sys.argv[1:])
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(2)
    print("STATIC_PASS provenance manifest consistency; registry attestation requires independent review")
