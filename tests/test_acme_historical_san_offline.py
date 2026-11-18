"""Historical #366 pure hypothesis tests."""
import pytest
from portal import acme_historical_san_offline as SAN

@pytest.mark.parametrize('scenario_id', [
    'FC_SFP_DEGRADATION', 'RHEL_MULTIPATH_FAILOVER',
    'DELL_PURE_CONTROLLER', 'NOISY_NEIGHBOR',
    'CAPACITY_PRESSURE', 'SAN_CHANGE_WINDOW', 'FALSE_POSITIVE_STORM'])
def test_forward_san_candidate_payments_and_erp_not_observed(scenario_id):
    result = SAN.scenario_assessment(scenario_id, {})
    assert result['candidate_impacted_services'] == sorted(SAN.SERVICES)
    assert result['observed_impacted_services'] == []
    assert result['decision'] == 'ABSTAIN'


def test_replication_lag_only_recovery_risk_not_payments_outage():
    result = SAN.scenario_assessment('REPLICATION_LAG', {})
    assert result['candidate_impacted_services'] == []
    assert result['recovery_exposure_services'] == sorted(SAN.SERVICES)
    assert result['decision'] == 'ABSTAIN'



@pytest.mark.parametrize('scenario_id', list(SAN.SCENARIOS))
def test_no_promotion_from_injected_provenance(scenario_id):
    value = SAN.scenario_assessment(scenario_id, {'runtime_attested': True, 'bound_run_id': 'FOREIGN'})
    assert value['runtime_attested'] is False
    assert value['topology']['runtime_attested'] is False
    assert value['topology']['bound_run_id'] is None
    assert value['decision'] == 'ABSTAIN'
    assert value['qualification'] == 'BLOCK'
    assert value['binding_status'] == 'UNBOUND'
    assert value['runtime_freshness'] == 'UNKNOWN'
    assert value['observed_impacted_services'] == []
