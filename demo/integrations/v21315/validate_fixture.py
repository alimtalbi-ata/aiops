#!/usr/bin/env python3
"""Fail-closed validation for the synthetic ACME V2.13.15 fixture.

This module is deliberately stdlib-only: it reads a local JSON file and never
contacts GLPI, Grafana, n8n, Core, a database, or any runtime service.
"""
from __future__ import annotations

import argparse
import heapq
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

TOP_LEVEL_FIELDS = {"schema", "provenance", "organization", "ci", "incidents"}
CI_FIELDS = {"id", "kind", "name", "depends_on"}
INCIDENT_FIELDS = {
    "id", "ci", "severity", "title", "status", "observation",
    "allowed_actions", "live_remediation",
}
SAFE_ACTIONS = {"analyze", "notify_dry_run"}
SEVERITIES = {"P1", "P2", "P3", "P4"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\\Z")

SOURCE_INCIDENT_ID = "ACME-DEMO-SAN-001"
SOURCE_CI_ID = "SAN-FABRIC-A"
TARGET_INCIDENT_ID = "ACME-DEMO-PAY-002"
TARGET_CI_ID = "APP-PAY-01"


def _require_fields(value: object, expected: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    actual = set(value)
    missing = sorted(str(key) for key in expected - actual)
    unexpected = sorted(str(key) for key in actual - expected)
    if missing or unexpected:
        raise ValueError(
            label + " fields mismatch (missing=" + repr(missing)
            + ", unexpected=" + repr(unexpected) + ")"
        )
    return value


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be a non-empty string")
    return value


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def load_fixture(path: str | Path) -> dict:
    """Load JSON without accepting duplicate object keys."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("cannot read fixture (" + type(exc).__name__ + ")") from exc
    try:
        value = json.loads(raw, object_pairs_hook=_unique_json_object)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "invalid fixture JSON at line " + str(exc.lineno)
            + ", column " + str(exc.colno)
        ) from exc
    if not isinstance(value, dict):
        raise ValueError("fixture root must be an object")
    return value


def _reject_dependency_cycles(dependencies: dict[str, list[str]]) -> None:
    """Validate the dependency DAG using Kahn's algorithm, deterministically."""
    remaining = {node: len(refs) for node, refs in dependencies.items()}
    consumers: dict[str, list[str]] = {node: [] for node in dependencies}
    for consumer, refs in dependencies.items():
        for dependency in refs:
            consumers[dependency].append(consumer)

    ready = [node for node, count in remaining.items() if count == 0]
    heapq.heapify(ready)
    visited = 0
    while ready:
        node = heapq.heappop(ready)
        visited += 1
        for consumer in sorted(consumers[node]):
            remaining[consumer] -= 1
            if remaining[consumer] == 0:
                heapq.heappush(ready, consumer)

    if visited != len(dependencies):
        cyclic = sorted(node for node, count in remaining.items() if count > 0)
        raise ValueError("CI dependency cycle detected: " + ", ".join(cyclic))


def _dependency_path(
    target: str, source: str, dependencies: dict[str, list[str]]
) -> list[str] | None:
    """Return deterministic source-to-target dependency path, or None."""
    pending = deque([(target, [target])])
    visited: set[str] = set()
    while pending:
        node, reverse_path = pending.popleft()
        if node == source:
            return list(reversed(reverse_path))
        if node in visited:
            continue
        visited.add(node)
        for dependency in sorted(dependencies[node]):
            pending.append((dependency, reverse_path + [dependency]))
    return None


def validate_fixture(data: object) -> dict:
    """Validate schema, safety invariants, DAG integrity and the ACME impact path."""
    fixture = _require_fields(data, TOP_LEVEL_FIELDS, "fixture")
    if fixture["schema"] != "aiops.acme.demo.v1":
        raise ValueError("unsupported fixture schema")
    if fixture["provenance"] != "SIMULATED_TARGET":
        raise ValueError("fixture provenance must be SIMULATED_TARGET")
    if fixture["organization"] != "ACME-DEMO":
        raise ValueError("fixture organization must be ACME-DEMO")

    raw_cis = fixture["ci"]
    if not isinstance(raw_cis, list) or len(raw_cis) < 6:
        raise ValueError("fixture must contain at least six CIs")

    cis: dict[str, dict] = {}
    dependencies: dict[str, list[str]] = {}
    for index, raw_ci in enumerate(raw_cis):
        ci = _require_fields(raw_ci, CI_FIELDS, "CI[" + str(index) + "]")
        ident = _require_text(ci["id"], "CI id")
        if not IDENTIFIER.fullmatch(ident):
            raise ValueError("invalid CI id: " + ident)
        if ident in cis:
            raise ValueError("duplicate CI id: " + ident)
        _require_text(ci["kind"], ident + ".kind")
        _require_text(ci["name"], ident + ".name")
        refs = ci["depends_on"]
        if not isinstance(refs, list) or any(
            not isinstance(ref, str) or not ref.strip() for ref in refs
        ):
            raise ValueError(ident + ".depends_on must be a list of CI IDs")
        if len(refs) != len(set(refs)):
            raise ValueError(ident + ".depends_on contains duplicate references")
        if ident in refs:
            raise ValueError(ident + " cannot depend on itself")
        cis[ident] = ci
        dependencies[ident] = list(refs)

    unknown = sorted({
        ref for refs in dependencies.values() for ref in refs if ref not in cis
    })
    if unknown:
        raise ValueError("unknown CI dependency: " + ", ".join(unknown))
    _reject_dependency_cycles(dependencies)

    raw_incidents = fixture["incidents"]
    if not isinstance(raw_incidents, list) or len(raw_incidents) < 2:
        raise ValueError("fixture must contain at least two incidents")

    incidents: dict[str, dict] = {}
    for index, raw_incident in enumerate(raw_incidents):
        incident = _require_fields(
            raw_incident, INCIDENT_FIELDS, "incident[" + str(index) + "]"
        )
        ident = _require_text(incident["id"], "incident id")
        if not IDENTIFIER.fullmatch(ident):
            raise ValueError("invalid incident id: " + ident)
        if ident in incidents:
            raise ValueError("duplicate incident id: " + ident)
        ci_id = _require_text(incident["ci"], ident + ".ci")
        if ci_id not in cis:
            raise ValueError(ident + " references an unknown CI")
        if incident["severity"] not in SEVERITIES:
            raise ValueError(ident + " has invalid severity")
        _require_text(incident["title"], ident + ".title")
        _require_text(incident["observation"], ident + ".observation")
        if incident["status"] != "simulated":
            raise ValueError(ident + " must remain simulated")
        if incident["live_remediation"] is not False:
            raise ValueError(ident + " must explicitly deny live remediation")
        actions = incident["allowed_actions"]
        if not isinstance(actions, list) or not actions or any(
            not isinstance(action, str) or not action for action in actions
        ):
            raise ValueError(ident + ".allowed_actions must be a non-empty string list")
        if len(actions) != len(set(actions)):
            raise ValueError(ident + " contains duplicate allowed actions")
        unexpected_actions = sorted(set(actions) - SAFE_ACTIONS)
        if unexpected_actions:
            raise ValueError(
                ident + " contains actions outside the simulation allowlist: "
                + ", ".join(unexpected_actions)
            )
        incidents[ident] = incident

    source = incidents.get(SOURCE_INCIDENT_ID)
    target = incidents.get(TARGET_INCIDENT_ID)
    if source is None or target is None:
        raise ValueError("canonical ACME SAN P1 and Payments P2 incidents are required")
    if source["severity"] != "P1" or source["ci"] != SOURCE_CI_ID:
        raise ValueError("canonical SAN source must be P1 on " + SOURCE_CI_ID)
    if target["severity"] != "P2" or target["ci"] != TARGET_CI_ID:
        raise ValueError("canonical Payments impact must be P2 on " + TARGET_CI_ID)

    impact_path = _dependency_path(TARGET_CI_ID, SOURCE_CI_ID, dependencies)
    if impact_path is None:
        raise ValueError(
            "Payments P2 has no transitive dependency path to the SAN P1 source"
        )

    return {
        "ci_count": len(cis),
        "incident_count": len(incidents),
        "source_incident_id": SOURCE_INCIDENT_ID,
        "target_incident_id": TARGET_INCIDENT_ID,
        "impact_path": impact_path,
        "provenance": "SIMULATED_TARGET",
        "live_remediation_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate synthetic ACME topology and SAN-to-Payments impact."
    )
    parser.add_argument(
        "fixture", nargs="?", type=Path, default=Path(__file__).with_name("acme-fixtures.json")
    )
    args = parser.parse_args(argv)
    try:
        report = validate_fixture(load_fixture(args.fixture))
    except (OSError, UnicodeError, ValueError) as exc:
        print("AIOPS_DEMO_FIXTURES=FAIL " + str(exc), file=sys.stderr)
        return 2

    path = " -> ".join(report["impact_path"])
    print(
        "AIOPS_DEMO_FIXTURES=PASS",
        report["ci_count"], "CIs", report["incident_count"], "incidents",
        "impact_path=" + path,
        "provenance=SIMULATED_TARGET",
        "live_remediation=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
