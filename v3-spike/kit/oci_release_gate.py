"""Fail-closed OCI BOM gate for a future V3 release (no registry access or deployment).

Input: JSON object {"schema_version":1,"images":[...]} with one entry per
required role. A digest string alone is never evidence of a real image.
"""
import argparse
import datetime as dt
import json
import re
import sys

ROLES = {"gamma", "core", "temporal", "worker", "policy", "hitl", "evidence"}
DIGEST = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
SPDX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")
ARCH = {"linux/amd64", "linux/arm64"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(doc):
    require(type(doc) is dict and set(doc) == {"schema_version", "images"}, "BOM schema keys")
    require(type(doc["schema_version"]) is int and doc["schema_version"] == 1, "BOM version")
    images = doc["images"]
    require(type(images) is list and len(images) == len(ROLES), "exactly seven required images")
    seen = set()
    required = {"role", "image", "source_commit", "source_path", "license_spdx",
                "platforms", "sbom_sha256", "provenance_sha256", "signature_sha256",
                "vulnerability_report_sha256", "ci_run_url", "ci_job_url", "verified_utc"}
    for item in images:
        require(type(item) is dict and set(item) == required, "image evidence schema")
        role = item["role"]
        require(type(role) is str and role in ROLES and role not in seen, "role missing/duplicate")
        seen.add(role)
        image = item["image"]
        require(type(image) is str and DIGEST.fullmatch(image) is not None, "immutable OCI reference")
        require(not image.startswith(("fixture/", "example.", "localhost/", "127.0.0.1/")),
                "synthetic/local image not eligible")
        require(type(item["source_commit"]) is str and SHA.fullmatch(item["source_commit"]) is not None,
                "source commit")
        require(type(item["source_path"]) is str and item["source_path"].startswith("https://")
                and "@" not in item["source_path"], "source path URL")
        require(type(item["license_spdx"]) is str and SPDX.fullmatch(item["license_spdx"]) is not None
                and item["license_spdx"] not in {"NOASSERTION", "NONE", "UNKNOWN"}, "license unresolved")
        platforms = item["platforms"]
        require(type(platforms) is list and len(platforms) > 0 and len(set(map(str, platforms))) == len(platforms)
                and all(type(p) is str and p in ARCH for p in platforms), "platforms")
        for field in ("sbom_sha256", "provenance_sha256", "signature_sha256",
                      "vulnerability_report_sha256"):
            value = item[field]
            require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                    field + " digest")
        for field in ("ci_run_url", "ci_job_url"):
            value = item[field]
            require(type(value) is str and re.fullmatch(
                r"https://github[.]com/[^/]+/[^/]+/actions/(?:runs|jobs)/[1-9][0-9]*", value
            ) is not None, field + " evidence URL")
        require("/runs/" in item["ci_run_url"] and "/jobs/" in item["ci_job_url"], "CI URL kinds")
        stamp = item["verified_utc"]
        require(type(stamp) is str and re.fullmatch(
            r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", stamp
        ) is not None, "UTC timestamp syntax")
        try:
            dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise ValueError("invalid UTC timestamp") from exc
    require(seen == ROLES, "required roles incomplete")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="local JSON evidence manifest; never commit secrets")
    args = parser.parse_args()
    try:
        with open(args.manifest, encoding="utf-8") as handle:
            validate(json.load(handle))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("OCI_BOM_FAIL: " + str(exc), file=sys.stderr)
        return 1
    print("OCI_BOM_STRUCTURE_PASS (not registry, signature, license or runtime attestation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
