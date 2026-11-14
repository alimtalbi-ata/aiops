"""Operator rehearsal must remain read-only and bound to the canonical package."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from package_aiops2_demo_evidence import create_package
from rehearse_aiops2_customer_demo import build_rehearsal


def test_rehearsal_contains_business_story_and_no_go(tmp_path):
    create_package(tmp_path / "demo", revision="test")
    text = build_rehearsal(tmp_path / "demo")
    assert "SAN → Payments" in text
    assert "DENY_LIVE_ACTION" in text
    assert "NO-GO" in text
    assert "UNKNOWN" in text
    assert "GLPI" in text
    assert "00–02" in text and "10–12" in text


def test_rehearsal_rejects_forged_runtime_claim(tmp_path):
    folder = tmp_path / "demo"
    create_package(folder, revision="test")
    path = folder / "cockpit.json"
    data = json.loads(path.read_text())
    data["runtime_attested"] = True
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="noncanonical_demo_package"):
        build_rehearsal(folder)


def test_rehearsal_rejects_missing_package(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_rehearsal(tmp_path / "missing")
