"""Produce a reproducible, offline ACME SAN->Payments demo acceptance report.

No network, no Temporal start, no GLPI writes, no LIVE remediation.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit


def build_report():
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    checks = {
        "synthetic_fixture": cockpit["mode"] == "DEMO"
            and cockpit["provenance"] == "LOCAL_SYNTHETIC_FIXTURE",
        "shared_source_digest": all(
            cockpit[key]["source_sha256"] == cockpit["source_sha256"]
            for key in ("lifecycle", "itil_readiness", "evidence_plan",
                        "analyst_critic_review")
        ),
        "incident_correlation": cockpit["incident_id"]
            == cockpit["evidence_plan"]["incident_id"]
            == cockpit["analyst_critic_review"]["incident_id"],
        "nine_lifecycle_stages": len(cockpit["lifecycle"]["stages"]) == 9,
        "eight_itil_gates": len(cockpit["itil_readiness"]["transitions"]) == 8,
        "no_verified_evidence": cockpit["evidence_plan"]["verified_count"] == 0,
        "no_runtime_citations": cockpit["analyst_critic_review"]["runtime_citations_verified"] == 0,
        "no_itil_authorization": cockpit["itil_readiness"]["authorized_transition_count"] == 0,
        "policy_denies_live": cockpit["analyst_critic_review"]["policy_disposition"]
            == "DENY_LIVE_ACTION",
        "runtime_unknown": cockpit["runtime_attested"] is False
            and cockpit["overall_qualification"] == "UNKNOWN",
        "live_disabled": cockpit["live_remediation_authorized"] is False,
    }
    return {
        "schema": "aiops2.demo-acceptance-report.v1",
        "scenario": "ACME-P1-SAN-PAYMENTS",
        "mode": "DEMO",
        "source_sha256": cockpit["source_sha256"],
        "incident_id": cockpit["incident_id"],
        "business_impact_incident_id": cockpit["business_impact_incident_id"],
        "checks": checks,
        "accepted": all(checks.values()),
        "runtime_execution_attested": False,
        "real_recovery_verified": False,
        "live_remediation_authorized": False,
    }


if __name__ == "__main__":
    try:
        report = build_report()
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"accepted": False, "reason": "invalid_synthetic_fixture",
                          "error_type": type(exc).__name__}))
        raise SystemExit(1)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["accepted"] else 1)
