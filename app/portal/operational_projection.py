"""Fail-closed read projection boundary, deliberately not connected to HTTP routes.

The trusted identity provider and per-tenant data source are prerequisites. This
module does not authenticate HTTP callers or confer authority on its own.
"""
from copy import deepcopy
from datetime import datetime, timezone
import math


class ProjectionDenied(Exception):
    """A caller has not been verified and authorized by the trusted server boundary."""


class ProjectionUnavailable(Exception):
    """The source cannot prove scope and observation freshness."""


def _timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ProjectionUnavailable("observation_timestamp_unverified")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectionUnavailable("observation_timestamp_unverified") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProjectionUnavailable("observation_timestamp_unverified")
    return parsed.astimezone(timezone.utc)


def project_authorized_records(*, identity, tenant_id, authorized_tenants, source, now=None, max_age_seconds=180):
    """Project only verified, tenant-scoped, fresh source records.

    All parameters MUST originate at the trusted server boundary; never bind
    identity, authorized_tenants or source verification to browser input.
    The source is a mapping with records, observed_at, tenant_id and
    scope_verified=True, produced by a separately authorized data query.
    """
    if not isinstance(identity, dict) or identity.get("verified") is not True or not isinstance(identity.get("actor_id"), str) or not identity["actor_id"].strip():
        raise ProjectionDenied("identity_not_verified")
    if not isinstance(tenant_id, str) or not tenant_id.strip() or not isinstance(authorized_tenants, (set, frozenset)) or tenant_id not in authorized_tenants:
        raise ProjectionDenied("tenant_not_authorized")
    if not isinstance(source, dict) or source.get("scope_verified") is not True or source.get("tenant_id") != tenant_id or not isinstance(source.get("records"), list):
        raise ProjectionUnavailable("source_scope_unverified")
    # Defense in depth: refuse mixed-tenant rows even when a source claims scope.
    if any(not isinstance(record, dict) or ("tenant_id" in record and record["tenant_id"] != tenant_id) for record in source["records"]):
        raise ProjectionUnavailable("source_scope_unverified")
    observed = _timestamp(source.get("observed_at"))
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None or isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, (int, float)) or not math.isfinite(max_age_seconds) or not 0 < max_age_seconds <= 3600:
        raise ProjectionUnavailable("freshness_policy_invalid")
    age = (current.astimezone(timezone.utc) - observed).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise ProjectionUnavailable("observation_not_fresh")
    return {"records": deepcopy(source["records"]), "observed_at": source["observed_at"], "scope_verified": True, "authorization_source": "server"}
