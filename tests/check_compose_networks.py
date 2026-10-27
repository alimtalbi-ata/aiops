#!/usr/bin/env python3
"""Fail CI if the isolated simulator cannot reach the authenticated Core API.

Input is the JSON produced by `docker compose config --format json`.
This is a network topology contract, not a runtime connectivity test.
"""
import json
import sys


def networks(services, name):
    service = services.get(name)
    if service is None:
        raise ValueError(f"missing service: {name}")
    configured = service.get("networks", {})
    if isinstance(configured, list):
        return set(configured)
    if isinstance(configured, dict):
        return set(configured)
    raise ValueError(f"unexpected networks for {name}")


def check(services):
    simulator = networks(services, "aiops2-simulator")
    core = networks(services, "aiops2-core")
    database = networks(services, "aiops2-postgres")
    worker = networks(services, "aiops2-worker")
    portal = networks(services, "aiops2-portal")

    if simulator != {"aiops2-execution"}:
        raise ValueError("simulator must remain isolated on aiops2-execution")
    if "aiops2-execution" not in core:
        raise ValueError("Core API is unreachable from the simulator execution network")
    if "aiops2-control" not in core or "aiops2-data" not in core:
        raise ValueError("Core lost its control or data network")
    if "aiops2-public" in core:
        raise ValueError("Core must not be directly attached to the public network")
    if simulator & database:
        raise ValueError("simulator must not share a network with PostgreSQL")
    if not (core & worker):
        raise ValueError("Core and Worker have no shared network")
    if not (core & portal):
        raise ValueError("Core and Portal have no shared network")


if __name__ == "__main__":
    try:
        document = json.load(sys.stdin)
        check(document["services"])
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"NETWORK_CONTRACT=FAIL|{exc}", file=sys.stderr)
        sys.exit(1)
    print("NETWORK_CONTRACT=PASS|simulator_core_reachable|data_isolated")
