import json
import datetime
import urllib.request
import urllib.parse

NOW = datetime.datetime.now(
    datetime.timezone.utc
).isoformat()

result = {
    "schema": "aiops2.fs374.services.v1",
    "collected_at": NOW,
    "sources": {},
    "remediation_executed": False
}

def fetch(name, url, kind="json"):
    try:
        with urllib.request.urlopen(
            url, timeout=3
        ) as response:
            raw = response.read(300000).decode(
                "utf-8", "replace"
            )

        if kind == "json":
            data = json.loads(raw)
            if isinstance(data, list):
                value = {
                    "count": len(data),
                    "sample": data[:2]
                }
            elif isinstance(data, dict):
                value = {
                    "keys": list(data)[:15],
                    "status": data.get("status"),
                    "data": str(
                        data.get("data", "")
                    )[:2500]
                }
            else:
                value = {"value": str(data)[:500]}
        else:
            lines = [
                x for x in raw.splitlines()
                if not x.startswith("#")
                and (
                    "aiops2_fs_lab" in x
                    or "filesystem" in x.lower()
                )
            ]
            value = {"metrics": lines[:25]}

        result["sources"][name] = {
            "available": True,
            "value": value
        }

    except Exception as exc:
        result["sources"][name] = {
            "available": False,
            "error": type(exc).__name__
        }

fetch(
    "core_incidents",
    "http://aiops2-core:810/api/incidents"
)

fetch(
    "core_runs",
    "http://aiops2-core:810/api/runs"
)

fetch(
    "worker_metrics",
    "http://aiops2-worker:815/metrics",
    "text"
)

query = urllib.parse.quote(
    "aiops2_fs_lab_used_percent"
)

fetch(
    "prometheus_fs_usage",
    "http://aiops2-prometheus:9090/api/v1/query"
    "?query=" + query
)

with open(
    "/tmp/fs374-services.json", "w"
) as f:
    json.dump(
        result,
        f,
        ensure_ascii=False,
        indent=2
    )

print(
    "FS374_SOURCES",
    json.dumps({
        name: value["available"]
        for name, value in result["sources"].items()
    })
)
