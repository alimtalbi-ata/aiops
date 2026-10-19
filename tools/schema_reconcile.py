#!/usr/bin/env python3
"""Compare legacy AIOps table names with read-only schema inventories.

This utility is intentionally offline and never connects to a database.
Matching names are review candidates, not proof of schema compatibility.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_legacy(path: Path) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        name = raw.strip()
        if name and not name.startswith("#"):
            names.add(name)
    return names


def read_inventory(path: Path) -> set[str]:
    names: set[str] = set()
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 1)
        if len(parts) != 2 or not all(part.strip() for part in parts):
            raise ValueError(f"{path}:{line_no}: expected schema|table")
        names.add(f"{parts[0].strip()}.{parts[1].strip()}")
    return names


def compare(legacy: set[str], v1: set[str], v2: set[str]) -> dict:
    v1_names = {item.rsplit(".", 1)[-1] for item in v1}
    v2_names = {item.rsplit(".", 1)[-1] for item in v2}
    rows = []
    for name in sorted(legacy | v1_names | v2_names):
        in_legacy, in_v1, in_v2 = name in legacy, name in v1_names, name in v2_names
        if in_legacy and in_v1 and in_v2:
            classification = "name-match-all-three"
        elif in_legacy and in_v2:
            classification = "legacy-and-v2-name-match"
        elif in_legacy and in_v1:
            classification = "legacy-and-v1-name-match"
        elif in_v2:
            classification = "v2-only-name"
        elif in_v1:
            classification = "v1-only-name"
        else:
            classification = "legacy-only-name"
        rows.append({
            "table": name,
            "legacy_r33": in_legacy,
            "v1_inventory": in_v1,
            "v2_inventory": in_v2,
            "classification": classification,
        })
    return {
        "method": "table-name-only",
        "warning": "Name overlap is not proof of schema, data, or semantic compatibility.",
        "counts": {
            "legacy_r33_names": len(legacy),
            "v1_distinct_names": len(v1_names),
            "v2_distinct_names": len(v2_names),
            "legacy_and_v2_name_matches": len(legacy & v2_names),
            "legacy_and_v1_name_matches": len(legacy & v1_names),
            "v1_and_v2_name_matches": len(v1_names & v2_names),
        },
        "rows": rows,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# AIOps schema name reconciliation",
        "",
        "> **Evidence boundary:** this report compares table names only. It does not inspect columns, constraints, data, or application behavior.",
        "",
        "## Counts",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {key.replace('_', ' ')} | {value} |" for key, value in report["counts"].items())
    lines += [
        "",
        "## Candidate inventory",
        "",
        "| Table name | R33 | V1 | V2 | Classification |",
        "|---|:---:|:---:|:---:|---|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| `{row['table']}` | {'yes' if row['legacy_r33'] else '—'} "
            f"| {'yes' if row['v1_inventory'] else '—'} "
            f"| {'yes' if row['v2_inventory'] else '—'} | {row['classification']} |"
        )
    lines += [
        "",
        "## Required next gate",
        "",
        "For every proposed reuse, compare column names/types, primary and foreign keys, indexes, nullability, constraints, row counts, data provenance, and owning service. Use a versioned adapter or migration plan; never restore the legacy dump over the active V2 database.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", required=True, type=Path, help="R33 table-name list, one name per line")
    parser.add_argument("--v1", required=True, type=Path, help="V1 inventory in schema|table format")
    parser.add_argument("--v2", required=True, type=Path, help="V2 inventory in schema|table format")
    parser.add_argument("--out", required=True, type=Path, help="Output directory")
    args = parser.parse_args()

    report = compare(read_legacy(args.legacy), read_inventory(args.v1), read_inventory(args.v2))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "schema-overlap.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "schema-overlap.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["counts"], sort_keys=True))
    print(f"REPORT_JSON={args.out / 'schema-overlap.json'}")
    print(f"REPORT_MD={args.out / 'schema-overlap.md'}")
    print("COMPATIBILITY_VERIFIED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
