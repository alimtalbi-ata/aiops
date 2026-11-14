"""Saved DEMO artifacts must match an independently recomputed local fixture."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts" / "run_acme_demo_simulation.py"
VERIFY = ROOT / "scripts" / "verify_acme_demo_simulation.py"


def _verify(path, tenant="acme-demo"):
    return subprocess.run([sys.executable, str(VERIFY), str(path),
                           "--expected-tenant", tenant],
                          cwd=ROOT, text=True, capture_output=True)


def test_saved_receipt_verified_and_tampering_rejected(tmp_path):
    run = subprocess.run([sys.executable, str(RUN), "--verify"],
                         cwd=ROOT, text=True, capture_output=True, check=True)
    path = tmp_path / "receipt.json"
    path.write_text(run.stdout)
    assert _verify(path).returncode == 0
    assert "LIVE_DENIED" in _verify(path).stdout
    assert _verify(path, tenant="other-tenant").returncode == 2
    data = json.loads(run.stdout)
    data["simulation"]["receipt"]["hypothetical_after"]["health"] = "DEGRADED"
    path.write_text(json.dumps(data))
    assert _verify(path).returncode == 2


def test_duplicate_keys_nonfinite_json_and_large_files_rejected(tmp_path):
    path = tmp_path / "receipt.json"
    for body in ('{"mode":"DEMO","mode":"LIVE"}',
                 '{"a":NaN}', "x" * (128 * 1024 + 1)):
        path.write_text(body)
        result = _verify(path)
        assert result.returncode == 2
        assert result.stdout == ""


def test_missing_file_and_symlink_rejected(tmp_path):
    path = tmp_path / "missing.json"
    assert _verify(path).returncode == 2
    target = tmp_path / "target.json"
    target.write_text("{}")
    path.symlink_to(target)
    assert _verify(path).returncode == 2
