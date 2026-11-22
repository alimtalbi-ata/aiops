"""Executable acceptance checks for the customer-visible ACME demo."""
import copy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_aiops2_demo_acceptance as demo


def test_operator_demo_report_is_traceable_and_no_go_live():
    report = demo.build_report()
    assert report["accepted"] is True
    assert all(report["checks"].values())
    assert len(report["source_sha256"]) == 64
    assert report["incident_id"]
    assert report["business_impact_incident_id"]
    assert report["runtime_execution_attested"] is False
    assert report["real_recovery_verified"] is False
    assert report["live_remediation_authorized"] is False


@pytest.mark.parametrize("path,value", [
    (("runtime_attested",), True),
    (("decision_preview", "policy", "decision"), "ALLOW_LIVE_ACTION"),
    (("checkpoint_evidence", 0, "status"), "PASS"),
])
def test_forged_runtime_success_fails_demonstration(path, value):
    from portal.acme_impact_read_model import build_acme_impact_read_model
    fixture = copy.deepcopy(build_acme_impact_read_model())
    target = fixture
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with patch.object(demo, "build_acme_impact_read_model", return_value=fixture):
        with pytest.raises(ValueError):
            demo.build_report()
