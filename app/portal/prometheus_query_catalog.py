"""Fixed Prometheus query catalog for a future trusted V30 server adapter.

No user-supplied PromQL, endpoint, label matcher, tenant selector or SQL is accepted.
This module does not perform I/O and does not attest a sample.
"""
from types import MappingProxyType

# Query names are API contract identifiers, not browser-provided expressions.
# Aggregation is intentionally host-wide: a server adapter MUST prove the
# Prometheus datasource and tenant isolation before enabling LIVE.
_QUERIES = MappingProxyType({
    "node_cpu_utilization": '1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))',
    "node_memory_used": 'sum(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)',
    "node_filesystem_available": 'sum(node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"})',
    "http_requests_rate": 'sum(rate(http_requests_total[2m]))',
})


def resolve_prometheus_query(*, metric, mode, server_authorized=False,
                             datasource_attested=False, tenant_isolated=False):
    """Return fixed query only after trusted server-side authorization.

    Flags MUST come from trusted server state; never bind them to request JSON.
    None means BLOCKED/UNKNOWN to the caller; it is never an empty healthy value.
    """
    if (type(metric) is not str or type(mode) is not str or mode != "LIVE"
            or server_authorized is not True or datasource_attested is not True
            or tenant_isolated is not True):
        return None
    return _QUERIES.get(metric)
