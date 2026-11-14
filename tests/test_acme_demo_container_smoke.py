"""Offline container smoke contract regression tests."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from portal.acme_demo_container_smoke import verify_packaged_demo


def test_packaged_demo_two_screens_remain_synthetic():
    result = verify_packaged_demo()
    assert result["accepted"] is True
    assert result["scope"] == "LOCAL_SYNTHETIC_ONLY"
    assert result["runtime_attested"] is False
    assert result["live_actions_authorized"] is False
    assert len(result["source_sha256"]) == 64


def test_packaged_demo_rejects_forged_positive_register():
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def forged(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            payload["decision"] = "GO_READ_ONLY_PILOT"
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=forged):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()


def test_packaged_demo_rejects_missing_customer_screen():
    import portal.acme_demo_container_smoke as smoke
    with patch.object(smoke, "acme_grafana_pilot_preview_page",
                      side_effect=ValueError("unavailable")):
        with pytest.raises(ValueError, match="unavailable"):
            verify_packaged_demo()

def test_packaged_demo_rejects_missing_evidence_source():
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def incomplete(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            del payload["sources"]["independent_postcheck"]
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=incomplete):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()
