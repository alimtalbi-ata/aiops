"""Read-only real Prometheus -> Twin scrape contract (ephemeral CI only).

A successful scrape proves metrics transport for the synthetic seed, not
tenant RBAC, a Payments incident, or any Debian deployment.
"""
from __future__ import annotations

import copy
import json
import os
import time
import unittest
import urllib.parse
import urllib.request


def validate_snapshot(targets: dict, up: dict, nodes: dict) -> None:
    """Reject absent, stale, duplicated or non-healthy real scrape evidence."""
    if targets.get("status") != "success":
        raise ValueError("targets_not_success")
    active = targets.get("data", {}).get("activeTargets", [])
    if not isinstance(active, list) or len(active) != 1:
        raise ValueError("ambiguous_twin_target")
    target = active[0]
    if (target.get("labels", {}).get("job") != "aiops2-twin"
            or target.get("scrapeUrl") != "http://127.0.0.1:811/metrics"
            or target.get("health") != "up"
            or target.get("lastError") != ""
            or not target.get("lastScrape")):
        raise ValueError("twin_scrape_not_up")
    for name, payload, expected in (("up", up, "1"), ("nodes", nodes, "25")):
        if (payload.get("status") != "success"
                or payload.get("data", {}).get("resultType") != "vector"):
            raise ValueError(name + "_query_failed")
        results = payload["data"].get("result", [])
        if not isinstance(results, list) or len(results) != 1:
            raise ValueError(name + "_query_ambiguous")
        item = results[0]
        if (item.get("metric", {}).get("job") != "aiops2-twin"
                or item.get("metric", {}).get("__name__") !=
                ("up" if name == "up" else "aiops_twin_nodes")
                or not isinstance(item.get("value"), list)
                or len(item["value"]) != 2 or item["value"][1] != expected):
            raise ValueError(name + "_query_mismatch")


def _query(path: str) -> dict:
    # Loopback only, no ambient proxy, no credentials in URLs or logs.
    url = "http://127.0.0.1:19090" + path
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=3) as response:
        if response.status != 200:
            raise ValueError("prometheus_http_error")
        return json.load(response)


class PrometheusTwinRealScrape(unittest.TestCase):
    def test_fail_closed_on_missing_or_forged_scrape(self):
        target = {"status": "success", "data": {"activeTargets": [{
            "labels": {"job": "aiops2-twin"},
            "scrapeUrl": "http://127.0.0.1:811/metrics",
            "health": "up", "lastError": "", "lastScrape": "ephemeral-ci",
        }]}}
        def metric(name: str, value: str) -> dict:
            return {"status": "success", "data": {"resultType": "vector",
                "result": [{"metric": {"job": "aiops2-twin", "__name__": name},
                            "value": [1, value]}]}}
        up, nodes = metric("up", "1"), metric("aiops_twin_nodes", "25")
        validate_snapshot(target, up, nodes)
        for name, t, u, n in (
            ("no_targets", {"status": "success", "data": {"activeTargets": []}}, up, nodes),
            ("down", {**target, "data": {"activeTargets": [
                {**target["data"]["activeTargets"][0], "health": "down"}]}}, up, nodes),
            ("wrong_nodes", target, up, metric("aiops_twin_nodes", "0")),
            ("missing_up", target, metric("up", "0"), nodes),
            ("duplicate", {**target, "data": {"activeTargets":
                target["data"]["activeTargets"] * 2}}, up, nodes),
        ):
            with self.subTest(case=name), self.assertRaises(ValueError):
                validate_snapshot(copy.deepcopy(t), copy.deepcopy(u), copy.deepcopy(n))

    @unittest.skipUnless(os.getenv("AIOPS_REAL_PROMETHEUS_TWIN_CI") == "true",
                         "real ephemeral Prometheus/Twin CI only")
    def test_real_prometheus_scrapes_twin_seed(self):
        query = lambda metric: "/api/v1/query?" + urllib.parse.urlencode(
            {"query": metric + '{job="aiops2-twin"}'})
        last_error = "not_yet_scraped"
        for _ in range(40):
            try:
                validate_snapshot(
                    _query("/api/v1/targets?state=active"),
                    _query(query("up")),
                    _query(query("aiops_twin_nodes")),
                )
                return
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                last_error = type(exc).__name__
                time.sleep(2)
        self.fail("BLOCKED: real Prometheus/Twin scrape not verified: " + last_error)


if __name__ == "__main__":
    unittest.main()
