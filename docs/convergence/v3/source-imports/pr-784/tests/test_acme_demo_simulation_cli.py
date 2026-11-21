"""The offline CLI emits a verified receipt and never promotes LIVE recovery."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_acme_demo_simulation.py"


def test_cli_verified_output_is_deterministic():
    command = [sys.executable, str(SCRIPT), "--verify"]
    first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    result = json.loads(first.stdout)
    assert result["mode"] == "DEMO"
    assert result["simulation"]["receipt"]["simulation_result"] == "HYPOTHETICAL_ONLY"
    assert result["evidence_gate"]["simulation_receipt_verified"] is True
    assert result["evidence_gate"]["actual_recovery_state"] == "UNKNOWN"
    assert result["live_remediation_authorized"] is False
    assert result["temporal_execution_performed"] is False
    assert result["glpi_write_performed"] is False


def test_cli_refuses_invalid_tenant_without_output():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--tenant", "../live", "--verify"],
        cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "refused" in result.stderr
