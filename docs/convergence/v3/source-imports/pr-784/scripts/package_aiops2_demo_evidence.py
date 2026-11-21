"""Generate an offline, verifiable ACME customer-demo evidence package.

No network calls or real service effects. All files are deterministic for a
given fixture and git revision. The manifest hashes package files only.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html
from verify_aiops2_demo_acceptance import build_report


def encode_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def git_revision():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"


def create_package(directory, revision=None):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("output directory must be empty")
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    report = build_report()
    if (not report["accepted"] or report["source_sha256"] != cockpit["source_sha256"]
            or report["incident_id"] != cockpit["incident_id"]
            or report["business_impact_incident_id"]
               != cockpit["business_impact_incident_id"]):
        raise ValueError("demo qualification and cockpit disagree")
    files = {
        "cockpit.json": encode_json(cockpit),
        "acceptance.json": encode_json(report),
        "cockpit.html": render_synthetic_cockpit_html(cockpit).encode("utf-8"),
    }
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (directory / name).write_bytes(data)
    manifest = {
        "schema": "aiops2.demo-evidence-package.v1",
        "scenario": "ACME-P1-SAN-PAYMENTS",
        "mode": "DEMO",
        "provenance": "LOCAL_SYNTHETIC_FIXTURE",
        "git_revision": revision if revision is not None else git_revision(),
        "source_sha256": report["source_sha256"],
        "incident_id": report["incident_id"],
        "business_impact_incident_id": report["business_impact_incident_id"],
        "files_sha256": {
            name: hashlib.sha256(data).hexdigest()
            for name, data in sorted(files.items())
        },
        "synthetic_acceptance_passed": True,
        "runtime_execution_attested": False,
        "real_recovery_verified": False,
        "live_remediation_authorized": False,
    }
    (directory / "manifest.json").write_bytes(encode_json(manifest))
    return manifest


def verify_package(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
    if (manifest.get("schema") != "aiops2.demo-evidence-package.v1"
            or manifest.get("mode") != "DEMO"
            or manifest.get("provenance") != "LOCAL_SYNTHETIC_FIXTURE"
            or manifest.get("synthetic_acceptance_passed") is not True
            or manifest.get("runtime_execution_attested") is not False
            or manifest.get("real_recovery_verified") is not False
            or manifest.get("live_remediation_authorized") is not False
            or set(manifest.get("files_sha256", {}))
               != {"cockpit.json", "acceptance.json", "cockpit.html"}
            or {p.name for p in directory.iterdir() if p.is_file()}
               != {"cockpit.json", "acceptance.json", "cockpit.html", "manifest.json"}):
        return False
    for name, digest in manifest["files_sha256"].items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            return False
    # Hashes alone are not trust: an attacker can rewrite both files and
    # manifest. Bind the package to this checkout's validated synthetic fixture.
    expected_cockpit = project_synthetic_incident_cockpit(
        build_acme_impact_read_model())
    expected_report = build_report()
    expected_files = {
        "cockpit.json": encode_json(expected_cockpit),
        "acceptance.json": encode_json(expected_report),
        "cockpit.html": render_synthetic_cockpit_html(expected_cockpit).encode("utf-8"),
    }
    if (manifest.get("scenario") != "ACME-P1-SAN-PAYMENTS"
            or manifest.get("source_sha256") != expected_report["source_sha256"]
            or manifest.get("incident_id") != expected_report["incident_id"]
            or manifest.get("business_impact_incident_id")
               != expected_report["business_impact_incident_id"]
            or any((directory / name).read_bytes() != expected_bytes
                   for name, expected_bytes in expected_files.items())):
        return False
    report = json.loads((directory / "acceptance.json").read_text("utf-8"))
    cockpit = json.loads((directory / "cockpit.json").read_text("utf-8"))
    return (report.get("accepted") is True
            and all(report.get("checks", {}).values())
            and report.get("runtime_execution_attested") is False
            and report.get("real_recovery_verified") is False
            and report.get("live_remediation_authorized") is False
            and report.get("source_sha256") == cockpit.get("source_sha256")
            == manifest.get("source_sha256")
            and report.get("incident_id") == cockpit.get("incident_id")
            == manifest.get("incident_id")
            and report.get("business_impact_incident_id")
            == cockpit.get("business_impact_incident_id")
            == manifest.get("business_impact_incident_id"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if (args.output is None) == (args.verify is None):
        parser.error("provide exactly one of --output or --verify")
    try:
        if args.output is not None:
            result = create_package(args.output)
            print(json.dumps(result, sort_keys=True))
        else:
            if not verify_package(args.verify):
                raise ValueError("package verification failed")
            print("DEMO package hashes and synthetic acceptance verified; runtime UNKNOWN")
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
