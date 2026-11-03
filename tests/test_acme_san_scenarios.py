"""ACME-TEST 019 topology / eight SAN hypotheses; no DB, network or LIVE writes."""
import importlib.util
import hashlib
import json
from decimal import Decimal
import re
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'app'
shared = types.ModuleType('shared')
shared.__path__ = []
db_module = types.ModuleType('shared.db')
db_module.db = lambda: None
sys.modules.setdefault('shared', shared)
sys.modules.setdefault('shared.db', db_module)
twin = types.ModuleType('twin')
twin.__path__ = [str(BASE / 'twin')]
sys.modules.setdefault('twin', twin)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load('twin.acme_sandbox', BASE / 'twin' / 'acme_sandbox.py')
SAN = load('twin.acme_san_scenarios', BASE / 'twin' / 'acme_san_scenarios.py')
TOKEN = 'test-internal-token-not-real'


class ReadOnlyGraph:
    def __init__(self):
        self.nodes = [(k, v, SAN.NODE_NAMES[k], SAN.SITE, 'SIMULATED', SAN.NODE_CRITICALITY[k], 1.0)
                      for k, v in SAN.NODES.items()]
        self.edges = [(k, *v, 1, 1.0) for k, v in SAN.EDGES.items()]
        self.sql = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql):
        self.sql.append(sql)
        if sql == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY':
            assert (len(self.sql) - 1) % 3 == 0, 'each snapshot starts with isolation'
            return None
        assert sql.strip().lower().startswith('select '), 'no writes allowed'
        assert self.sql[(len(self.sql) - 1) // 3 * 3] == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
        if 'twin_nodes' in sql:
            # Model the actual SQL predicate: unrelated IDs in the sandbox
            # site must be visible to the exact-nine-node verifier.
            return Cursor([row for row in self.nodes if row[0].startswith('ACME-TEST-')
                           or ("site = 'ACME-TEST-SIMULATION'" in sql and row[3] == SAN.SITE)])
        assert 'twin_edges' in sql
        # Emulate the edge-ID and both endpoint predicates, including foreign
        # endpoints hidden behind an ACME-TEST edge identifier.
        return Cursor([row for row in self.edges
                       if (("edge_id like 'ACME-TEST-%'" in sql and row[0].startswith('ACME-TEST-'))
                           or row[1].startswith('ACME-TEST-')
                           or row[2].startswith('ACME-TEST-'))])


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


@pytest.fixture
def graph(monkeypatch):
    g = ReadOnlyGraph()
    monkeypatch.setattr(SAN, 'db', lambda: g)
    monkeypatch.setenv('AIOPS_ACME_SANDBOX_ENABLED', 'true')
    monkeypatch.setenv('AIOPS_INTERNAL_TOKEN', TOKEN)
    monkeypatch.setenv('AIOPS_ACME_TWIN_APPROVAL_KEY', 'sandbox-test-key-longer-than-32-bytes')
    return g


def test_migration_019_has_exact_independent_9_node_8_edge_contract():
    sql = (ROOT / 'db/migrations/019_acme_sandbox_twin_topology.sql').read_text()
    assert len(SAN.NODES) == 9 and len(SAN.EDGES) == 8
    assert len(SAN.NODE_CRITICALITY) == 9 and len(SAN.NODE_NAMES) == 9
    assert set(SAN.NODE_CRITICALITY) == set(SAN.NODES)
    assert set(SAN.NODE_NAMES) == set(SAN.NODES)
    for node, node_type in SAN.NODES.items():
        assert f"('{node}','{node_type}','{SAN.NODE_NAMES[node]}'," in sql
    for edge, (src, dst, relation) in SAN.EDGES.items():
        assert f"('{edge}','{src}','{dst}','{relation}',1,1.0,now())" in sql
    assert 'acme_sandbox_twin_node_provenance_conflict' in sql
    assert 'acme_sandbox_twin_edge_provenance_conflict' in sql
    assert set(SAN.SCENARIOS) == {
        'FC_SFP_DEGRADATION', 'RHEL_MULTIPATH_FAILOVER',
        'DELL_PURE_CONTROLLER', 'NOISY_NEIGHBOR', 'REPLICATION_LAG',
        'CAPACITY_PRESSURE', 'SAN_CHANGE_WINDOW', 'FALSE_POSITIVE_STORM'}


def test_catalog_eight_hypotheses_abstain_without_analyst_critic(graph):
    result = SAN.catalog(authorization='Bearer ' + TOKEN)
    assert result['schema'] == 'aiops.acme-san-scenario-catalog.v1'
    assert len(result['scenarios']) == 8
    assert result['topology']['nodes'] == 9
    assert result['topology']['edges'] == 8
    assert re.fullmatch('[0-9a-f]{64}', result['topology']['graph_sha256'])
    for scenario in result['scenarios']:
        assert scenario['tenant_id'] == 'ACME-TEST'
        assert scenario['topology']['graph_sha256'] == result['topology']['graph_sha256']
        assert 'graph' not in scenario['topology']  # single catalog graph, not eight copies
        assert scenario['mode'] == 'SIMULATION'
        assert scenario['evidence']['status'] == 'NOT_OBSERVED'
        assert scenario['evidence']['required_independent_fields']
        assert scenario['analyst']['status'] == 'NOT_ATTESTED'
        assert scenario['critic']['status'] == 'NOT_ATTESTED'
        assert scenario['decision'] == 'ABSTAIN'
        assert scenario['observed_impacted_services'] == []
        assert scenario['human_approved'] is False
        assert scenario['effect_allowed'] is False
        assert scenario['live_effects_allowed'] is False
        assert scenario['real_glpi_writes_allowed'] is False
    assert len(graph.sql) == 3
    assert graph.sql[0] == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    assert all(sql.strip().lower().startswith('select ') for sql in graph.sql[1:])



def test_verified_pg19_graph_is_ui_ready_but_not_a_run_observation(graph):
    topology = SAN.provenance_snapshot()
    view = topology['graph']
    assert len(view['nodes']) == 9 and len(view['edges']) == 8
    assert {n['node_id'] for n in view['nodes']} == set(SAN.NODES)
    assert {e['edge_id'] for e in view['edges']} == set(SAN.EDGES)
    assert all(n['site'] == SAN.SITE and n['state'] == 'SIMULATED'
               for n in view['nodes'])
    assert view['paths'] == {
        'fabric_a_to_payments': [SAN.A, SAN.H, SAN.PAYMENTS],
        'fabric_b_to_payments': [SAN.B, SAN.H, SAN.PAYMENTS],
        'fabric_a_to_erp': [SAN.A, SAN.H, SAN.ERP],
        'fabric_b_to_erp': [SAN.B, SAN.H, SAN.ERP],
    }
    assert view['runtime_attested'] is False
    assert view['bound_run_id'] is None
    assert view['observed_at_utc'] is None
    assert view['source_time'] == 'MIGRATION_019_NOT_AN_OBSERVATION'
    nodes = sorted((n['node_id'], n['type'], n['name'], n['site'],
                    n['state'], n['criticality'], n['confidence']) for n in view['nodes'])
    edges = sorted((e['edge_id'], e['source_id'], e['target_id'],
                    e['relation_type'], e['redundancy'], e['confidence']) for e in view['edges'])
    assert hashlib.sha256(json.dumps(
        {'nodes': nodes, 'edges': edges}, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest() == topology['graph_sha256']
    assert json.loads(json.dumps(topology))['graph'] == view


@pytest.mark.parametrize('scenario_id', [
    'FC_SFP_DEGRADATION', 'RHEL_MULTIPATH_FAILOVER',
    'DELL_PURE_CONTROLLER', 'NOISY_NEIGHBOR',
    'CAPACITY_PRESSURE', 'SAN_CHANGE_WINDOW', 'FALSE_POSITIVE_STORM'])
def test_forward_san_candidate_payments_and_erp_not_observed(graph, scenario_id):
    result = SAN.get_scenario(scenario_id, authorization='Bearer ' + TOKEN)
    assert result['candidate_impacted_services'] == sorted(SAN.SERVICES)
    assert result['observed_impacted_services'] == []
    assert result['decision'] == 'ABSTAIN'


def test_replication_lag_only_recovery_risk_not_payments_outage(graph):
    result = SAN.get_scenario('REPLICATION_LAG', authorization='Bearer ' + TOKEN)
    assert result['candidate_impacted_services'] == []
    assert result['recovery_exposure_services'] == sorted(SAN.SERVICES)
    assert result['decision'] == 'ABSTAIN'


@pytest.mark.parametrize('mutation', [
    'node_missing', 'node_extra', 'node_foreign_same_site', 'node_site_live', 'node_state_live',
    'node_wrong_type', 'node_wrong_name', 'node_low_confidence', 'node_wrong_criticality', 'edge_missing',
    'edge_extra', 'edge_foreign_inbound', 'edge_acme_id_foreign_endpoints', 'edge_wrong_relation',
    'edge_swapped_fabrics', 'edge_low_confidence', 'edge_bad_redundancy',
    'edge_duplicate',
])
def test_provenance_rejects_drift_mixed_live_and_foreign_edges(graph, mutation):
    if mutation == 'node_missing':
        graph.nodes.pop()
    elif mutation == 'node_extra':
        graph.nodes.append(('ACME-TEST-FOREIGN', 'SIMULATED_SAN_ARRAY', 'foreign SAN', SAN.SITE, 'SIMULATED', 5, 1.0))
    elif mutation == 'node_foreign_same_site':
        graph.nodes.append(('UNPREFIXED-SAN-NODE', 'SIMULATED_SAN_ARRAY', 'foreign SAN', SAN.SITE, 'SIMULATED', 5, 1.0))
    elif mutation.startswith('node_'):
        row = list(graph.nodes[0])
        row[{'node_site_live': 3, 'node_state_live': 4,
             'node_wrong_type': 1, 'node_wrong_name': 2,
             'node_low_confidence': 6, 'node_wrong_criticality': 5}[mutation]] = {
                 'node_site_live': 'PARIS', 'node_state_live': 'LIVE',
                 'node_wrong_type': 'REAL_SAN_ARRAY',
                 'node_wrong_name': 'LIVE array masquerading as ACME-TEST',
                 'node_low_confidence': 0.3,
                 'node_wrong_criticality': 1}[mutation]
        graph.nodes[0] = tuple(row)
    elif mutation == 'edge_missing':
        graph.edges.pop()
    elif mutation == 'edge_extra':
        graph.edges.append(('ACME-TEST-SIM-EDGE-009', SAN.A, SAN.PAYMENTS, 'SIMULATED_DEPENDS_ON', 1, 1.0))
    elif mutation == 'edge_foreign_inbound':
        graph.edges.append(('FOREIGN-EDGE', 'LIVE-ARRAY', SAN.A, 'REAL_DEPENDS_ON', 1, 1.0))
    elif mutation == 'edge_acme_id_foreign_endpoints':
        graph.edges.append(('ACME-TEST-SIM-EDGE-009', 'LIVE-ARRAY-A', 'LIVE-ARRAY-B',
                            'REAL_DEPENDS_ON', 1, 1.0))
    elif mutation == 'edge_duplicate':
        graph.edges.append(graph.edges[0])
    else:
        row = list(graph.edges[0])
        if mutation == 'edge_wrong_relation':
            row[3] = 'REAL_FC_PATH'
        elif mutation == 'edge_swapped_fabrics':
            row[2] = SAN.B
        elif mutation == 'edge_low_confidence':
            row[5] = 0.2
        else:
            row[4] = 0
        graph.edges[0] = tuple(row)
    with pytest.raises(HTTPException) as err:
        SAN.provenance_snapshot()
    assert err.value.status_code == 503
    assert err.value.detail == 'acme_san_topology_provenance_unqualified'



def test_unrelated_foreign_edge_does_not_poison_sandbox_provenance(graph):
    graph.edges.append(('FOREIGN-EDGE', 'LIVE-ARRAY-A', 'LIVE-ARRAY-B',
                        'REAL_DEPENDS_ON', 1, 1.0))
    assert SAN.provenance_snapshot()['edges'] == 8


def test_snapshot_isolation_precedes_node_and_edge_reads(graph):
    receipt = SAN.provenance_snapshot()
    assert receipt['nodes'] == 9 and receipt['edges'] == 8
    assert len(graph.sql) == 3
    assert graph.sql[0] == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    assert 'twin_nodes' in graph.sql[1]
    assert "site = 'ACME-TEST-SIMULATION'" in graph.sql[1]
    assert 'twin_edges' in graph.sql[2]
    assert "edge_id like 'ACME-TEST-%'" in graph.sql[2]


def test_snapshot_setup_failure_never_returns_provenance(graph, monkeypatch):
    class RejectIsolation(ReadOnlyGraph):
        def execute(self, sql):
            if sql.startswith('SET TRANSACTION'):
                raise RuntimeError('isolation unavailable')
            return super().execute(sql)
    broken = RejectIsolation()
    monkeypatch.setattr(SAN, 'db', lambda: broken)
    with pytest.raises(RuntimeError, match='isolation unavailable'):
        SAN.provenance_snapshot()
    assert broken.sql == []

def test_digest_is_deterministic_independent_of_db_order(graph):
    first = SAN.provenance_snapshot()['graph_sha256']
    graph.nodes.reverse()
    graph.edges.reverse()
    assert SAN.provenance_snapshot()['graph_sha256'] == first


def test_digest_binds_criticality_confidence_and_redundancy(graph):
    receipt = SAN.provenance_snapshot()
    normalized = {
        'nodes': sorted(graph.nodes),
        'edges': sorted(graph.edges),
    }
    expected = hashlib.sha256(json.dumps(
        normalized, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert receipt['graph_sha256'] == expected
    # The prior weak digest omitted operational criticality and edge confidence.
    old = {
        'nodes': sorted((node_id, node_type, site, state)
                        for node_id, node_type, _, site, state, _, _ in graph.nodes),
        'edges': sorted((edge_id, source, target, relation)
                        for edge_id, source, target, relation, _, _ in graph.edges),
    }
    old_digest = hashlib.sha256(json.dumps(
        old, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert receipt['graph_sha256'] != old_digest


def test_pg_numeric_decimal_confidence_has_stable_digest(graph):
    baseline = SAN.provenance_snapshot()['graph_sha256']
    graph.nodes = [(*row[:-1], Decimal('1.0')) for row in graph.nodes]
    graph.edges = [(*row[:-1], Decimal('1.0')) for row in graph.edges]
    assert SAN.provenance_snapshot()['graph_sha256'] == baseline


def test_no_token_or_disabled_sandbox_never_reads_graph(graph, monkeypatch):
    with pytest.raises(HTTPException) as err:
        SAN.catalog(authorization='Bearer forged')
    assert err.value.status_code == 401
    assert graph.sql == []
    monkeypatch.setenv('AIOPS_ACME_SANDBOX_ENABLED', 'false')
    with pytest.raises(HTTPException) as err:
        SAN.catalog(authorization='Bearer ' + TOKEN)
    assert err.value.status_code == 503
    assert graph.sql == []


def test_unknown_scenario_denied_without_promotion(graph):
    with pytest.raises(HTTPException) as err:
        SAN.get_scenario('LIVE_EXECUTE', authorization='Bearer ' + TOKEN)
    assert err.value.status_code == 404


def test_endpoint_registered_only_as_read_only_get():
    methods = {tuple(sorted(route.methods)) for route in SAN.router.routes}
    assert methods == {('GET',)}
    main = (BASE / 'twin/main.py').read_text()
    assert 'app.include_router(acme_san_scenarios_router)' in main
