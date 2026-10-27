#!/usr/bin/env python3
"""Backward-compatible offline CLI for the shared ACME fixture contract.

The canonical validator is packaged with the portal image. This wrapper keeps
the historical demo CLI and its import surface without maintaining a second
copy of the dependency-graph validation rules.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from portal.acme_fixture_contract import (  # noqa: E402
    CI_FIELDS,
    IDENTIFIER,
    INCIDENT_FIELDS,
    SAFE_ACTIONS,
    SEVERITIES,
    SOURCE_CI_ID,
    SOURCE_INCIDENT_ID,
    TARGET_CI_ID,
    TARGET_INCIDENT_ID,
    TOP_LEVEL_FIELDS,
    load_fixture,
    load_fixture_bytes,
    validate_fixture,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate synthetic ACME topology and SAN-to-Payments impact."
    )
    parser.add_argument(
        "fixture",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("acme-fixtures.json"),
    )
    args = parser.parse_args(argv)
    try:
        report = validate_fixture(load_fixture(args.fixture))
    except (OSError, UnicodeError, ValueError) as exc:
        print("AIOPS_DEMO_FIXTURES=FAIL " + str(exc), file=sys.stderr)
        return 2

    path = " -> ".join(report["impact_path"])
    blast_radius = ",".join(report["affected_ci_ids"])
    print(
        "AIOPS_DEMO_FIXTURES=PASS",
        report["ci_count"], "CIs", report["incident_count"], "incidents",
        "impact_path=" + path,
        "affected_cis=" + blast_radius,
        "provenance=SIMULATED_TARGET",
        "live_remediation=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
