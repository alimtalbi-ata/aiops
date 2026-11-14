"""An actual callable DEMO path, with no fabricated runtime recovery."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_demo_simulation_pipeline import run_acme_demo_simulation


def test_pipeline_is_deterministic_and_incident_bound():
    result = run_acme_demo_simulation()
    assert result == run_acme_demo_simulation()
    assert result["mode"] == "DEMO"
    assert result["incident_id"] == result["evidence_gate"]["incident_id"]
    assert result["source_sha256"] == result["evidence_gate"]["source_sha256"]
    assert result["simulation"]["receipt"]["incident_id"] == result["incident_id"]
    assert result["simulation"]["receipt"]["hypothetical_after"]["health"] == "HEALTHY"
    assert result["evidence_gate"]["actual_recovery_state"] == "UNKNOWN"
    assert result["evidence_gate"]["evidence_integrity_consistent_unattested_count"] == 0
    assert result["evidence_gate"]["independent_runtime_postcheck_verified"] is False
    assert result["runtime_execution_performed"] is False
    assert result["glpi_write_performed"] is False
    assert result["temporal_execution_performed"] is False
    assert result["live_remediation_authorized"] is False


def test_tenant_is_scoped_and_no_live_fallback():
    result = run_acme_demo_simulation(tenant_id="tenant-two")
    assert result["evidence_gate"]["tenant_id"] == "tenant-two"
    assert result["simulation"]["receipt"]["tenant_id"] == "tenant-two"
    with pytest.raises(ValueError):
        run_acme_demo_simulation(tenant_id="")
