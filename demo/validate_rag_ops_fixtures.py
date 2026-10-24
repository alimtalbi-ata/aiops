"""Validate the simulated multi-vendor RAG catalog; no external calls."""
from __future__ import annotations
import json
from pathlib import Path

KINDS = {"EVENT_CATALOG", "RUNBOOK", "SNMP_MIB"}
SIGNALS = {"SYSLOG", "SNMP_TRAP", "METRIC", "LOG"}
REQUIRED = {"doc_id", "vendor", "product", "kind", "signal_type", "event_key", "sample", "asset", "service", "runbook", "source_type"}

def validate_catalog(data: dict) -> int:
    if not isinstance(data, dict) or data.get("schema") != "aiops-rag-ops-synthetic-fixtures-v1" or data.get("provenance") != "SYNTHETIC_SIMULATION_ONLY":
        raise ValueError("invalid synthetic RAG catalog")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 100:
        raise ValueError("invalid fixture count")
    seen = set()
    for row in scenarios:
        if not isinstance(row, dict) or set(row) != REQUIRED:
            raise ValueError("unexpected catalog fields")
        if row["source_type"] != "SYNTHETIC" or row["kind"] not in KINDS or row["signal_type"] not in SIGNALS:
            raise ValueError("catalog attempted to claim vendor authority")
        for key in REQUIRED - {"runbook"}:
            if not isinstance(row[key], str) or not row[key] or len(row[key]) > 1024:
                raise ValueError("invalid catalog field: " + key)
        if not row["sample"].startswith("DEMO ONLY:") or row["doc_id"] in seen:
            raise ValueError("unlabeled or duplicate synthetic case")
        if not isinstance(row["runbook"], list) or not row["runbook"] or any(not isinstance(x, str) or not x for x in row["runbook"]):
            raise ValueError("invalid runbook")
        seen.add(row["doc_id"])
    return len(scenarios)

if __name__ == "__main__":
    data = json.loads((Path(__file__).resolve().parent / "rag_ops_fixture_catalog.json").read_text(encoding="utf-8"))
    print("AIOPS_SYNTHETIC_RAG_FIXTURES_VALID=" + str(validate_catalog(data)))
