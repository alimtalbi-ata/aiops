"""Offline, synthetic-only dependency proof projection; never queries CMDB."""
from datetime import datetime

SCHEMA = 'aiops2.twin-proof-boundary.v1'
KINDS = ('SAN', 'STORAGE', 'SERVICE')


def _time(value):
    if type(value) is not str or not value.endswith('Z'):
        raise ValueError('UTC timestamp required')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def project(nodes, relations, *, tenant, now, max_age_seconds=900):
    """Return two ordered edges; unproven links remain UNKNOWN, never inferred."""
    if type(tenant) is not str or not tenant or type(max_age_seconds) is not int or max_age_seconds < 0:
        raise ValueError('invalid scope/freshness')
    current = _time(now)
    if type(nodes) is not list or type(relations) is not list:
        raise ValueError('invalid fixture')
    by_kind = {}
    for node in nodes:
        if type(node) is not dict or set(node) != {'id', 'kind', 'tenant'}:
            raise ValueError('invalid node')
        if node['tenant'] != tenant or node['kind'] not in KINDS or type(node['id']) is not str or not node['id']:
            raise ValueError('cross-tenant/invalid node')
        if node['kind'] in by_kind or node['id'] in [n['id'] for n in by_kind.values()]:
            raise ValueError('ambiguous node')
        by_kind[node['kind']] = node
    output = []
    for src_kind, dst_kind in (('SAN', 'STORAGE'), ('STORAGE', 'SERVICE')):
        src, dst = by_kind.get(src_kind), by_kind.get(dst_kind)
        matches = []
        for edge in relations:
            if type(edge) is not dict or set(edge) != {'source', 'target', 'tenant', 'authority', 'evidence_id', 'observed_at', 'attested'}:
                raise ValueError('invalid edge')
            if edge['tenant'] != tenant:
                raise ValueError('cross-tenant edge')
            if edge['source'] not in [n['id'] for n in by_kind.values()] or edge['target'] not in [n['id'] for n in by_kind.values()]:
                raise ValueError('dangling edge')
            if src and dst and edge['source'] == src['id'] and edge['target'] == dst['id']:
                matches.append(edge)
        status = 'UNKNOWN'
        if len(matches) == 1:
            e = matches[0]
            age = (current - _time(e['observed_at'])).total_seconds()
            if e['authority'] == 'CMDB' and type(e['evidence_id']) is str and e['evidence_id'] and e['attested'] is True and 0 <= age <= max_age_seconds:
                status = 'SOURCED_SYNTHETIC'
        output.append({'from': src_kind, 'to': dst_kind, 'status': status})
    return {'schema': SCHEMA, 'mode': 'DEMO', 'tenant': tenant, 'edges': output, 'live_attested': False}
