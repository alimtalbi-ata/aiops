"""Offline historical scenario catalog #366 cec48fa2a0e5976be90d3cebcdf929d05835a58f; no DB or route."""
from collections import deque
from fastapi import HTTPException

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
        'topology': {'provenance': 'SYNTHETIC_FIXTURE_ONLY', 'runtime_attested': False,
                     'bound_run_id': None, 'observed_at_utc': None},
        'runtime_attested': False, 'binding_status': 'UNBOUND',
        'runtime_freshness': 'UNKNOWN', 'qualification': 'BLOCK', 'trigger_nodes': list(roots),
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


