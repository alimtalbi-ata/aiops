"""ACME SAN->Payments read-only Core binding *probe*, not tenant attestation.

Consumes the pinned seven-event synthetic replay. The current Core GET routes
expose a public Run registry/detail and an internal-Bearer NOC projection, but
do NOT expose an independently actor+tenant-authorized Incident/Run readback.
A matching internal pair is therefore explicitly UNKNOWN, never a receipt.
No writes, no GLPI/Evidence lookup, no HITL/effect/model claims.
"""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import json
import os
import re
from urllib.error import HTTPError, URLError

from tools import acme_synthetic_receipt_reconciliation as receipts
from tools import find_acme_demo_run as locator
from tools import generate_acme_incidents as gen

_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")
_MAX_AGE = timedelta(hours=24)


def _fresh(stamp, now):
    if type(stamp) is not str or _STAMP.fullmatch(stamp) is None:
        return False
    try:
        value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if value.utcoffset() is None:
            return False
        age = now - value.astimezone(timezone.utc)
        return -timedelta(minutes=5) <= age <= _MAX_AGE
    except (ValueError, OverflowError, TypeError):
        return False


def _untrusted_claims(row):
    # The currently supported read model has no authenticated actor/tenant
    # binding. Caller- or server-added claims cannot silently upgrade it.
    return any(key in row for key in ("tenant_id", "actor_subject",
                                      "actor_verified", "tenant_authenticated"))


def probe_core_binding_readonly(manifest, *, origin=None, expected_run_id=None,
                                expected_incident_id=None, token=None,
                                test_partition="SYNTHETIC_TEST_PARTITION_A",
                                now=None, get=None):
    """Read three existing Core GETs; never promote them to tenant authority.

    Expected IDs are operator-provided search hints, NOT fixture-derived IDs.
    Even a matching internal Bearer response cannot establish actor identity,
    tenant ACL, seven-event Core ingestion, Evidence or GLPI reconciliation.
    """
    offline = receipts.reconcile_fixture_receipts_offline(
        manifest, test_partition=test_partition)
    result = {
        "schema": "aiops.acme.core-readonly-binding-probe.v1",
        "result": "UNKNOWN",
        "reason": "NOT_PROBED",
        "authority": "CORE_INTERNAL_BEARER_ONLY_NOT_TENANT_AUTHORITY",
        "synthetic": True,
        "source_manifest_sha256": offline["source_manifest_sha256"],
        "canonical_replay_file_sha256": offline["canonical_replay_file_sha256"],
        "source_event_count": 7,
        "seed": offline["seed"],
        "graph_version": offline["graph_version"],
        "test_partition": offline["test_partition"],
        "test_partition_is_tenant_authority": False,
        "tenant_id": None, "actor_subject": None,
        "incident_id": None, "run_id": None, "glpi_ticket_id": None,
        "evidence_ids": [],
        "tenant_acl_qualified": False,
        "actor_authenticated": False,
        "runtime_attested": False,
        "source_event_binding_verified": False,
        "core_internal_pair_match": False,
        "core_read_attempt_count": 0,
        "observed_impact": "UNKNOWN",
        "priority_confirmed": "UNKNOWN",
        "runtime_readback": "NOT_EXECUTED",
        "stages": copy.deepcopy(offline["stages"]),
        "checkpoints": copy.deepcopy(offline["checkpoints"]),
    }
    def unknown(reason):
        result["reason"] = reason
        return result

    if (type(expected_run_id) is not str or
            locator.RUN_ID.fullmatch(expected_run_id) is None or
            type(expected_incident_id) is not str or
            locator.INCIDENT_ID.fullmatch(expected_incident_id) is None):
        return unknown("EXPECTED_CORE_PAIR_UNKNOWN")
    if type(token) is not str or not token:
        return unknown("INTERNAL_TOKEN_NOT_CONFIGURED")
    if not locator._safe_url(origin):
        return unknown("CORE_ORIGIN_NOT_PINNED")
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return unknown("INVALID_PROBE_CLOCK")
    now = now.astimezone(timezone.utc)
    get = locator.fetch_json if get is None else get
    rid, iid = expected_run_id, expected_incident_id
    try:
        result["core_read_attempt_count"] += 1
        registry = get(origin, "/api/runs")
        result["core_read_attempt_count"] += 1
        detail = get(origin, "/api/runs/" + rid)
        result["core_read_attempt_count"] += 1
        internal = get(origin, "/api/noc/runs/" + rid, token=token)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError,
            KeyError, json.JSONDecodeError):
        return unknown("CORE_READ_UNAVAILABLE")
    # The public list is a bounded window; absence is UNKNOWN, not a 404 proof.
    if (type(registry) is not dict or type(registry.get("items")) is not list or
            len(registry["items"]) > 100):
        return unknown("REGISTRY_UNQUALIFIED")
    matches = [row for row in registry["items"]
               if type(row) is dict and row.get("run_id") == rid]
    if len(matches) != 1:
        return unknown("RUN_NOT_UNIQUELY_IN_REGISTRY_WINDOW")
    row = matches[0]
    if (row.get("incident_id") != iid or row.get("scenario_id") != locator.SCENARIO
            or row.get("mode") != "DEMO" or type(row.get("status")) is not str
            or _untrusted_claims(row)):
        return unknown("RUN_REGISTRY_SCOPE_OR_SCENARIO_MISMATCH")
    if not _fresh(row.get("created_at"), now):
        return unknown("RUN_SOURCE_TIMESTAMP_STALE_OR_MISSING")
    if type(detail) is not dict or type(detail.get("run")) is not dict:
        return unknown("RUN_DETAIL_MISSING")
    canonical = detail["run"]
    if (_untrusted_claims(canonical) or
            any(canonical.get(key) != row.get(key) for key in
                ("run_id", "incident_id", "scenario_id", "mode", "status", "created_at"))):
        return unknown("RUN_DETAIL_SCOPE_MISMATCH")
    events = detail.get("events")
    if (type(events) is not list or not events or len(events) > 1000 or
            any(type(e) is not dict or
                ("run_id" in e and e["run_id"] != rid) for e in events)):
        return unknown("RUN_EVENTS_UNQUALIFIED")
    first = events[0]
    if (first.get("sequence") != 1 or first.get("event_type") != "RUN_CREATED"
            or first.get("stage") != "INGEST" or
            type(first.get("payload")) is not dict or
            first["payload"].get("scenario_id") != locator.SCENARIO or
            first["payload"].get("mode") != "DEMO"):
        return unknown("RUN_CREATION_ANCHOR_MISMATCH")
    if (type(internal) is not dict or type(internal.get("run")) is not dict
            or _untrusted_claims(internal) or _untrusted_claims(internal["run"])
            or internal.get("data_classification") != "SYNTHETIC_CANONICAL_RUN"
            or internal.get("tenant_acl_qualified") is not False
            or internal.get("runtime_authenticated") is not False
            or internal.get("live_remediation_authorized") is not False
            or any(internal["run"].get(key) != row.get(key) for key in
                   ("run_id", "incident_id", "mode", "status"))):
        return unknown("INTERNAL_PROJECTION_UNQUALIFIED")
    result["core_internal_pair_match"] = True
    result["runtime_readback"] = "INTERNAL_READ_ONLY_NOT_TENANT_ATTESTED"
    return unknown("TENANT_ACTOR_AND_CANONICAL_EVENT_BINDING_UNAVAILABLE")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-url", required=True)
    parser.add_argument("--expect-run-id", required=True)
    parser.add_argument("--expect-incident-id", required=True)
    args = parser.parse_args(argv)
    result = probe_core_binding_readonly(
        gen.replay(), origin=args.core_url, expected_run_id=args.expect_run_id,
        expected_incident_id=args.expect_incident_id,
        token=os.environ.get("AIOPS_INTERNAL_TOKEN"))
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("stages", "checkpoints")}, sort_keys=True))
    return 2  # No current Core GET can independently attest tenant+actor.


if __name__ == "__main__":
    raise SystemExit(main())
