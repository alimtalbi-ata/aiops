#!/usr/bin/env python3
"""Aggregate repeated AIOps Analyst/Critic benchmark reports without inventing usage or cost."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METRICS = (
    "severity_accuracy", "grounding", "freshness_accuracy", "action_safety",
    "injection_resistance", "contradiction_detection", "stale_detection",
    "critic_disposition", "proposal_actionability", "action_target_accuracy",
    "action_type_validity", "action_evidence_grounding",
    "precondition_completeness", "postcondition_testability", "rollback_completeness",
    "latency_ms_p50", "latency_ms_p95", "usage_coverage", "retry_count",
    "successful_calls", "failed_calls", "request_count_total",
)

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def read_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError(f"{path}: report must be an object")
    if report.get("mode") not in ("DEMO", "REPLAY", "STORY"):
        raise ValueError(f"{path}: non-synthetic benchmark mode refused")
    if report.get("execution_allowed") is not False:
        raise ValueError(f"{path}: execution authority must remain false")
    if not report.get("dataset_sha256") or not report.get("model") or not report.get("provider"):
        raise ValueError(f"{path}: dataset/provider/model identity required")
    if not isinstance(report.get("metrics"), dict):
        raise ValueError(f"{path}: metrics object required")
    return report

def median_metric(reports: list[dict[str, Any]], key: str) -> float | None:
    values = []
    for report in reports:
        value = report["metrics"].get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return round(statistics.median(values), 4) if len(values) == len(reports) else None

def aggregate_reports(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("no benchmark reports found")
    reports = [read_report(path) for path in sorted(paths)]
    dataset_hashes = {report["dataset_sha256"] for report in reports}
    if len(dataset_hashes) != 1:
        raise ValueError("dataset SHA-256 differs across repeats; reports are not comparable")
    prompt_versions = {report.get("prompt_version", "UNKNOWN") for report in reports}
    if len(prompt_versions) != 1:
        raise ValueError("prompt versions differ across repeats; reports are not comparable")

    groups: dict[tuple[str, str], list[tuple[Path, dict[str, Any]]]] = {}
    for path, report in zip(sorted(paths), reports):
        groups.setdefault((str(report["provider"]), str(report["model"])), []).append((path, report))

    model_results = []
    for (provider, model), entries in sorted(groups.items()):
        group = [entry[1] for entry in entries]
        metrics = {key: median_metric(group, key) for key in METRICS}
        complete = [r for r in group if r["metrics"].get("token_totals_complete") is True
                    and isinstance(r["metrics"].get("total_tokens"), int)]
        costs = [r["metrics"].get("cost_usd") for r in group]
        error_classes = {}
        for report in group:
            classes = report["metrics"].get("error_classes", {})
            if isinstance(classes, dict):
                for name, count in classes.items():
                    if isinstance(name, str) and type(count) is int and count > 0:
                        error_classes[name] = error_classes.get(name, 0) + count
        costs_complete = bool(costs) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in costs)
        token_values = [r["metrics"]["total_tokens"] for r in complete]
        # A zero coverage value means no provider usage was observed, not a
        # measured zero-token result. Keep it UNKNOWN; positive ratios remain
        # useful for partially reported usage even when total token sums are incomplete.
        coverage_values = [
            float(r["metrics"]["usage_coverage"])
            for r in group
            if isinstance(r["metrics"].get("usage_coverage"), (int, float))
            and not isinstance(r["metrics"].get("usage_coverage"), bool)
            and r["metrics"]["usage_coverage"] > 0
        ]
        model_results.append({
            "provider": provider,
            "model": model,
            "repeats": len(group),
            "evaluation_passes": sum(r.get("result") == "PASS" for r in group),
            "evaluation_failures": sum(r.get("result") != "PASS" for r in group),
            "quality_pass_rate": round(sum(r.get("result") == "PASS" for r in group) / len(group), 4),
            "metrics_median": metrics,
            "error_classes": error_classes,
            "usage_complete_repeats": len(complete),
            "usage_coverage_mean": round(statistics.mean(coverage_values), 4)
                if len(coverage_values) == len(group) else None,
            "total_tokens_mean": round(statistics.mean(token_values), 2) if len(complete) == len(group) else None,
            "prompt_tokens_mean": round(statistics.mean(
                r["metrics"]["prompt_tokens_total"] for r in complete
            ), 2) if len(complete) == len(group) else None,
            "completion_tokens_mean": round(statistics.mean(
                r["metrics"]["completion_tokens_total"] for r in complete
            ), 2) if len(complete) == len(group) else None,
            "cost_usd_mean": round(statistics.mean(costs), 8) if costs_complete else None,
            "cost_status": "MEASURED" if costs_complete else "UNKNOWN_OR_PARTIAL",
            "per_run": [{
                "file": path.name,
                "sha256": sha256(path),
                "evaluation_id": report.get("evaluation_id"),
                "result": report.get("result"),
                "cases_total": report["metrics"].get("cases_total"),
                "cases_analyzed": report["metrics"].get("cases_analyzed"),
                "model_calls": report["metrics"].get("model_calls"),
                "successful_calls": report["metrics"].get("successful_calls"),
                "failed_calls": report["metrics"].get("failed_calls"),
                "error_classes": report["metrics"].get("error_classes"),
                "usage_coverage": report["metrics"].get("usage_coverage"),
                "total_tokens": report["metrics"].get("total_tokens")
                    if report["metrics"].get("token_totals_complete") is True else None,
                "latency_ms_p50": report["metrics"].get("latency_ms_p50"),
                "latency_ms_p95": report["metrics"].get("latency_ms_p95"),
                "cost_usd": report["metrics"].get("cost_usd"),
                "cost_status": report["metrics"].get("cost_status"),
            } for path, report in entries],
        })

    return {
        "qualification": "AIOps real local-model benchmark aggregation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": next(iter(dataset_hashes)),
        "prompt_version": next(iter(prompt_versions)),
        "qualification_kinds": sorted({str(r.get("qualification_kind", "UNKNOWN")) for r in reports}),
        "mode": "SYNTHETIC_ONLY",
        "execution_allowed": False,
        "reports_total": len(reports),
        "model_results": model_results,
        "cost_policy": "No price inference; cost remains null unless every repeat supplies priced cost.",
        "limitations": [
            "Local Ollama CPU inference is not DGX/NVIDIA NIM qualification.",
            "Synthetic dataset results are not customer incident accuracy or production SLA evidence.",
            "Provider-reported token usage is retained only when the provider reports complete usage.",
            "A benchmark execution can complete while a model's quality gates fail; inspect evaluation_passes and per-run results.",
        ],
    }

def markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# AIOps local-model benchmark summary",
        "",
        f"- Dataset SHA-256: `{summary['dataset_sha256']}`",
        f"- Prompt: `{summary['prompt_version']}`",
        f"- Reports: {summary['reports_total']}",
        "- Mode: SYNTHETIC_ONLY; execution_allowed=false",
        "",
        "| Model | Repeats | Eval pass | Calls OK/failed | Usage coverage | Severity | Grounding | Critic | P50 ms | P95 ms | Tokens/repeat | Cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in summary["model_results"]:
        m = item["metrics_median"]
        def fmt(value):
            return "UNKNOWN" if value is None else str(value)
        lines.append(
            f"| {item['model']} | {item['repeats']} | "
            f"{item['evaluation_passes']}/{item['repeats']} | "
            f"{fmt(m['severity_accuracy'])} | {fmt(m['grounding'])} | "
            f"{fmt(m['critic_disposition'])} | {fmt(m['latency_ms_p50'])} | "
            f"{fmt(m['latency_ms_p95'])} | {fmt(item['total_tokens_mean'])} | "
            f"{fmt(item['cost_usd_mean'])} |"
        )
    lines += ["", "Cost is not estimated. UNKNOWN means no complete, pinned pricing evidence."]
    return "\n".join(lines) + "\n"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--json-out", default="reports/ai-benchmark-summary.json")
    parser.add_argument("--markdown-out", default="reports/ai-benchmark-summary.md")
    args = parser.parse_args()
    directory = Path(args.reports_dir)
    paths = sorted(directory.glob("*-repeat-*.json"))
    result = aggregate_reports(paths)
    json_path, md_path = Path(args.json_out), Path(args.markdown_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown(result), encoding="utf-8")
    print(f"BENCHMARK_REPORTS={result['reports_total']}")
    for model in result["model_results"]:
        print(f"MODEL={model['model']}|PASS={model['evaluation_passes']}/{model['repeats']}|"
              f"P50={model['metrics_median']['latency_ms_p50']}|"
              f"P95={model['metrics_median']['latency_ms_p95']}|"
              f"TOKENS={model['total_tokens_mean']}|COST={model['cost_usd_mean']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
