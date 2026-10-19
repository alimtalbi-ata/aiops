#!/usr/bin/env python3
"""Compare PostgreSQL schema fingerprints without reading application rows."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format_version") != 1 or not isinstance(data.get("relations"), list):
        raise ValueError(f"{path}: unsupported or malformed schema fingerprint")
    return data


def keyed(relations: list[dict]) -> dict[str, dict]:
    result = {}
    for rel in relations:
        key = f"{rel['schema']}.{rel['name']}"
        if key in result:
            raise ValueError(f"duplicate relation key: {key}")
        result[key] = rel
    return result


def compare(left: dict, right: dict) -> dict:
    a, b = keyed(left["relations"]), keyed(right["relations"])
    rows = []
    for name in sorted(set(a) | set(b)):
        if name not in a:
            rows.append({"relation": name, "status": "right-only", "differences": []})
            continue
        if name not in b:
            rows.append({"relation": name, "status": "left-only", "differences": []})
            continue
        differences = []
        for field in ("kind", "columns", "constraints", "indexes"):
            if a[name].get(field) != b[name].get(field):
                differences.append(field)
        rows.append({
            "relation": name,
            "status": "identical" if not differences else "different",
            "differences": differences,
        })
    return {
        "format_version": 1,
        "method": "schema-fingerprint-structural-comparison",
        "left_database": left.get("database"),
        "right_database": right.get("database"),
        "warning": "Structural equality does not establish data equivalence, API compatibility, or safe migration.",
        "counts": {
            "left_relations": len(a),
            "right_relations": len(b),
            "identical": sum(row["status"] == "identical" for row in rows),
            "different": sum(row["status"] == "different" for row in rows),
            "left_only": sum(row["status"] == "left-only" for row in rows),
            "right_only": sum(row["status"] == "right-only" for row in rows),
        },
        "relations": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path, help="First fingerprint JSON")
    parser.add_argument("right", type=Path, help="Second fingerprint JSON")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path")
    args = parser.parse_args()
    report = compare(load(args.left), load(args.right))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], sort_keys=True))
    print(f"REPORT={args.out}")
    print("MIGRATION_SAFETY_VERIFIED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
