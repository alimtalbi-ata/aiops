"""Read-only ACME-TEST SAN scenario catalog with exact migration-019 provenance.

Never promotes hypothetical evidence to observed impact, Analyst/Critic approval,
human authority or LIVE execution. This endpoint has no write path.
"""
import hashlib
import json
from collections import deque

from fastapi import APIRouter, Header, HTTPException
from shared.db import db
from twin.acme_sandbox import auth, require_enabled

router = APIRouter()
SITE = 'ACME-TEST-SIMULATION'
TENANT = 'ACME-TEST'
PAYMENTS = 'ACME-TEST-SVC-PAYMENTS'
ERP = 'ACME-TEST-SVC-ERP'
SERVICES = frozenset((PAYMENTS, ERP))
NODES = {
    'ACME-TEST-SAN-ARRAY-DELL-01': 'SIMULATED_SAN_ARRAY',
    'ACME-TEST-SAN-ARRAY-PURE-01': 'SIMULATED_SAN_ARRAY',
    'ACME-TEST-SAN-FABRIC-A': 'SIMULATED_FC_FABRIC',
    'ACME-TEST-SAN-FABRIC-B': 'SIMULATED_FC_FABRIC',
    'ACME-TEST-HOST-RHEL-MPATH-01': 'SIMULATED_RHEL_MULTIPATH',
    PAYMENTS: 'SIMULATED_BUSINESS_SERVICE',
    ERP: 'SIMULATED_BUSINESS_SERVICE',
    'ACME-TEST-SAN-REPLICATION-01': 'SIMULATED_REPLICATION',
    'ACME-TEST-SAN-BACKUP-01': 'SIMULATED_BACKUP',
}
NODE_NAMES = {
    'ACME-TEST-SAN-ARRAY-DELL-01': 'ACME-TEST Dell SAN array',
    'ACME-TEST-SAN-ARRAY-PURE-01': 'ACME-TEST Pure SAN array',
    'ACME-TEST-SAN-FABRIC-A': 'ACME-TEST FC fabric A',
    'ACME-TEST-SAN-FABRIC-B': 'ACME-TEST FC fabric B',
    'ACME-TEST-HOST-RHEL-MPATH-01': 'ACME-TEST RHEL multipath host',
    PAYMENTS: 'ACME-TEST payments service',
    ERP: 'ACME-TEST ERP service',
    'ACME-TEST-SAN-REPLICATION-01': 'ACME-TEST replication target',
    'ACME-TEST-SAN-BACKUP-01': 'ACME-TEST backup target',
}
NODE_CRITICALITY = {
    'ACME-TEST-SAN-ARRAY-DELL-01': 5,
    'ACME-TEST-SAN-ARRAY-PURE-01': 5,
    'ACME-TEST-SAN-FABRIC-A': 5,
    'ACME-TEST-SAN-FABRIC-B': 5,
    'ACME-TEST-HOST-RHEL-MPATH-01': 5,
    PAYMENTS: 5,
    ERP: 4,
    'ACME-TEST-SAN-REPLICATION-01': 3,
    'ACME-TEST-SAN-BACKUP-01': 3,
}
EDGES = {
    'ACME-TEST-SIM-EDGE-001': ('ACME-TEST-SAN-ARRAY-DELL-01', 'ACME-TEST-SAN-FABRIC-A', 'SIMULATED_FC_PATH'),
    'ACME-TEST-SIM-EDGE-002': ('ACME-TEST-SAN-ARRAY-PURE-01', 'ACME-TEST-SAN-FABRIC-B', 'SIMULATED_FC_PATH'),
    'ACME-TEST-SIM-EDGE-003': ('ACME-TEST-SAN-FABRIC-A', 'ACME-TEST-HOST-RHEL-MPATH-01', 'SIMULATED_FC_PATH'),
    'ACME-TEST-SIM-EDGE-004': ('ACME-TEST-SAN-FABRIC-B', 'ACME-TEST-HOST-RHEL-MPATH-01', 'SIMULATED_FC_PATH'),
    'ACME-TEST-SIM-EDGE-005': ('ACME-TEST-HOST-RHEL-MPATH-01', PAYMENTS, 'SIMULATED_DEPENDS_ON'),
    'ACME-TEST-SIM-EDGE-006': ('ACME-TEST-HOST-RHEL-MPATH-01', ERP, 'SIMULATED_DEPENDS_ON'),
    'ACME-TEST-SIM-EDGE-007': ('ACME-TEST-SAN-ARRAY-DELL-01', 'ACME-TEST-SAN-REPLICATION-01', 'SIMULATED_REPLICATION'),
    'ACME-TEST-SIM-EDGE-008': ('ACME-TEST-SAN-ARRAY-PURE-01', 'ACME-TEST-SAN-BACKUP-01', 'SIMULATED_BACKUP'),
}
A = 'ACME-TEST-SAN-FABRIC-A'
B = 'ACME-TEST-SAN-FABRIC-B'
H = 'ACME-TEST-HOST-RHEL-MPATH-01'
D = 'ACME-TEST-SAN-ARRAY-DELL-01'
P = 'ACME-TEST-SAN-ARRAY-PURE-01'
R = 'ACME-TEST-SAN-REPLICATION-01'
# (trigger roots, required independent telemetry, Analyst question, Critic challenge)
SCENARIOS = {
    'FC_SFP_DEGRADATION': ((A, B), ('fc_port_id', 'sfp_crc_errors', 'link_state', 'observed_at'),
                           'Is the optic/FC port actually degrading?', 'Check both fabrics and independent switch counters.'),
    'RHEL_MULTIPATH_FAILOVER': ((H,), ('dm_wwid', 'multipath_path_states', 'kernel_events', 'observed_at'),
                                'Did RHEL lose usable SAN paths?', 'Check healthy alternate paths and independent host logs.'),
    'DELL_PURE_CONTROLLER': ((D, P), ('array_vendor', 'controller_event_id', 'controller_state', 'observed_at'),
                             'Is a Dell or Pure controller degraded?', 'Separate array events from fabric and host symptoms.'),
    'NOISY_NEIGHBOR': ((H,), ('workload_id', 'io_latency', 'iops', 'qos_counters', 'observed_at'),
                       'Is workload contention causing latency?', 'Require a causal baseline, not latency correlation alone.'),
    'REPLICATION_LAG': ((R,), ('replication_pair_id', 'lag_seconds', 'rpo_seconds', 'observed_at'),
                        'Is recovery protection degraded?', 'Replication lag alone does not prove Payments outage.'),
    'CAPACITY_PRESSURE': ((D, P), ('array_id', 'used_capacity_pct', 'growth_rate', 'observed_at'),
                          'Is storage capacity approaching a hard limit?', 'Confirm headroom, thin provisioning and thresholds.'),
    'SAN_CHANGE_WINDOW': ((A, B), ('change_id', 'change_window', 'fabric_config_diff', 'observed_at'),
                          'Did a controlled change precede the signal?', 'Do not infer causality from timing alone.'),
    'FALSE_POSITIVE_STORM': ((A, B), ('alert_ids', 'dedup_fingerprint', 'baseline', 'observed_at'),
                             'Are correlated alerts duplicates/noise?', 'Abstain until independent corroboration and deduplication.'),
}


def provenance_snapshot():
    """Verify exactly 9 synthetic nodes/8 edges, including *inbound* foreign links."""
    with db() as conn:
        # Both SELECTs must observe one PG snapshot; READ COMMITTED could
        # otherwise mix pre-change nodes with post-change edges.
        # This transaction is read-only and never mutates the graph.
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        nodes = conn.execute(
            "select node_id,type,name,site,state,criticality,confidence from aiops.twin_nodes "
            "where node_id like 'ACME-TEST-%' or site = 'ACME-TEST-SIMULATION'").fetchall()
        edges = conn.execute(
            "select edge_id,source_id,target_id,relation_type,redundancy,confidence "
            "from aiops.twin_edges where edge_id like 'ACME-TEST-%' or source_id like 'ACME-TEST-%' "
            "or target_id like 'ACME-TEST-%'").fetchall()
    if (len(nodes) != 9 or len(edges) != 8
            or len({row[0] for row in nodes}) != 9
            or len({row[0] for row in edges}) != 8):
        raise HTTPException(503, 'acme_san_topology_provenance_unqualified')
    for node_id, node_type, name, site, state, criticality, confidence in nodes:
        if (NODES.get(node_id) != node_type or NODE_NAMES.get(node_id) != name
                or site != SITE
                or state != 'SIMULATED' or NODE_CRITICALITY.get(node_id) != criticality
                or confidence != 1):
            raise HTTPException(503, 'acme_san_topology_provenance_unqualified')
    for edge_id, source, target, relation, redundancy, confidence in edges:
        if (EDGES.get(edge_id) != (source, target, relation)
                or redundancy != 1 or confidence != 1):
            raise HTTPException(503, 'acme_san_topology_provenance_unqualified')
    normalized = {
        'nodes': sorted((node_id, node_type, name, site, state, criticality, float(confidence))
                        for node_id, node_type, name, site, state, criticality, confidence in nodes),
        'edges': sorted((edge_id, source, target, relation, redundancy, float(confidence))
                        for edge_id, source, target, relation, redundancy, confidence in edges),
    }
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    # Expose the *verified PG19 graph*, not the unrelated six-CI portal fixture.
    # These are synthetic topology facts, NOT an observation or a Run join.
    graph_nodes = [
        {'node_id': node_id, 'type': node_type, 'name': name, 'site': site,
         'state': state, 'criticality': criticality, 'confidence': confidence}
        for node_id, node_type, name, site, state, criticality, confidence in normalized['nodes']
    ]
    graph_edges = [
        {'edge_id': edge_id, 'source_id': source, 'target_id': target,
         'relation_type': relation, 'redundancy': redundancy, 'confidence': confidence}
        for edge_id, source, target, relation, redundancy, confidence in normalized['edges']
    ]
    graph_paths = {
        'fabric_a_to_payments': [A, H, PAYMENTS],
        'fabric_b_to_payments': [B, H, PAYMENTS],
        'fabric_a_to_erp': [A, H, ERP],
        'fabric_b_to_erp': [B, H, ERP],
    }
    actual_links = {(edge['source_id'], edge['target_id']) for edge in graph_edges}
    if any(any(pair not in actual_links for pair in zip(path, path[1:]))
           for path in graph_paths.values()):
        raise HTTPException(503, 'acme_san_topology_provenance_unqualified')
    return {'schema': 'aiops.acme-test-san-topology.v1', 'source_migration': '019',
            'tenant_id': TENANT, 'site': SITE, 'provenance': 'SYNTHETIC_FIXTURE_ONLY',
            'nodes': 9, 'edges': 8, 'graph_sha256': digest,
            'graph': {'nodes': graph_nodes, 'edges': graph_edges, 'paths': graph_paths,
                      'runtime_attested': False, 'bound_run_id': None,
                      'observed_at_utc': None,
                      'source_time': 'MIGRATION_019_NOT_AN_OBSERVATION'}}


def _reachable(roots, reverse=False):
    adjacency = {node_id: set() for node_id in NODES}
    for source, target, _ in EDGES.values():
        if reverse:
            source, target = target, source
        adjacency[source].add(target)
    seen, queue = set(), deque(roots)
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(adjacency[node] - seen)
    return seen


def scenario_assessment(scenario_id, provenance):
    if scenario_id not in SCENARIOS:
        raise HTTPException(404, 'acme_san_scenario_unknown')
    roots, evidence, analyst, critic = SCENARIOS[scenario_id]
    candidate = sorted(_reachable(roots) & SERVICES)
    recovery = []
    if scenario_id == 'REPLICATION_LAG':
        # A replication target is downstream of an array, not an outage source.
        ancestors = _reachable(roots, reverse=True)
        recovery = sorted(_reachable(ancestors) & SERVICES)
    return {
        'scenario_id': scenario_id, 'tenant_id': TENANT, 'mode': 'SIMULATION',
        'topology': provenance, 'trigger_nodes': list(roots),
        'candidate_impacted_services': candidate, 'observed_impacted_services': [],
        'recovery_exposure_services': recovery,
        'evidence': {'status': 'NOT_OBSERVED', 'required_independent_fields': list(evidence),
                     'source': 'NO_INDEPENDENT_TELEMETRY'},
        'analyst': {'status': 'NOT_ATTESTED', 'question': analyst},
        'critic': {'status': 'NOT_ATTESTED', 'challenge': critic},
        'decision': 'ABSTAIN', 'reason': 'INDEPENDENT_EVIDENCE_AND_ANALYST_CRITIC_MISSING',
        'human_approved': False, 'effect_allowed': False,
        'live_effects_allowed': False, 'real_glpi_writes_allowed': False,
    }


@router.get('/api/sandbox/acme/san-scenarios')
def catalog(authorization: str | None = Header(default=None)):
    auth(authorization)
    require_enabled()
    provenance = provenance_snapshot()
    # One graph per catalog, not eight repeated copies; scenario references
    # retain the exact digest but cannot be mistaken for Run-bound observations.
    summary = {key: value for key, value in provenance.items() if key != 'graph'}
    return {'schema': 'aiops.acme-san-scenario-catalog.v1', 'tenant_id': TENANT,
            'mode': 'SIMULATION', 'topology': provenance,
            'scenarios': [scenario_assessment(key, summary) for key in SCENARIOS],
            'no_live_or_human_authority': True}


@router.get('/api/sandbox/acme/san-scenarios/{scenario_id}')
def get_scenario(scenario_id: str, authorization: str | None = Header(default=None)):
    auth(authorization)
    require_enabled()
    provenance = provenance_snapshot()
    return scenario_assessment(scenario_id, provenance)
