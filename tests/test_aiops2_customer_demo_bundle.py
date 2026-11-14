"""Synthetic cross-artifact consistency regression; no external network."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_aiops2_customer_demo_bundle import verify_bundle, build_qualification_report


def test_bundle_accepts_same_canonical_incident_and_run(tmp_path):
    pkg, smoke_dir = tmp_path / "package", tmp_path / "smoke"
    pkg.mkdir()
    smoke_dir.mkdir()
    sha = "a" * 40
    fixture = "b" * 64
    manifest = {"git_revision": sha, "incident_id": "SAN-P1",
                "source_sha256": fixture,
                "runtime_execution_attested": False,
                "live_remediation_authorized": False}
    cockpit = {"incident_id": "SAN-P1", "source_sha256": fixture}
    smoke = {"incident_id": "SAN-P1", "source_sha256": fixture}
    provenance = {"run_id": "123", "commit_sha": sha}
    for directory, name, value in (
        (pkg, "manifest.json", manifest),
        (pkg, "cockpit.json", cockpit),
        (smoke_dir, "aiops2-packaged-demo-smoke.json", smoke),
        (smoke_dir, "aiops2-packaged-demo-smoke-provenance.json", provenance),
    ):
        (directory / name).write_text(json.dumps(value), encoding="utf-8")

    def check():
        return verify_bundle(pkg, smoke_dir, repository="alimtalbi-ata/aiops",
                             head_sha=sha, run_id="123", run_attempt="1")

    with patch("verify_aiops2_customer_demo_bundle.verify_package", return_value=True), \
         patch("verify_aiops2_customer_demo_bundle.verify_smoke", return_value=True):
        assert check()
        smoke["incident_id"] = "OTHER-P1"
        (smoke_dir / "aiops2-packaged-demo-smoke.json").write_text(json.dumps(smoke))
        assert not check()
        smoke["incident_id"] = "SAN-P1"
        smoke["source_sha256"] = "c" * 64
        (smoke_dir / "aiops2-packaged-demo-smoke.json").write_text(json.dumps(smoke))
        assert not check()
        smoke["source_sha256"] = fixture
        (smoke_dir / "aiops2-packaged-demo-smoke.json").write_text(json.dumps(smoke))
        manifest["git_revision"] = "d" * 40
        (pkg / "manifest.json").write_text(json.dumps(manifest))
        assert not check()
        manifest["git_revision"] = sha
        manifest["live_remediation_authorized"] = True
        (pkg / "manifest.json").write_text(json.dumps(manifest))
        assert not check()


def test_bundle_fails_closed_if_smoke_provenance_invalid(tmp_path):
    with patch("verify_aiops2_customer_demo_bundle.verify_package", return_value=True), \
         patch("verify_aiops2_customer_demo_bundle.verify_smoke", return_value=False):
        assert not verify_bundle(tmp_path, tmp_path, repository="r", head_sha="a" * 40,
                                 run_id="1", run_attempt="1")


def test_bundle_fails_closed_on_missing_files(tmp_path):
    assert not verify_bundle(tmp_path, tmp_path, repository="r", head_sha="a" * 40,
                             run_id="1", run_attempt="1")


def test_bundle_accepts_pr_merge_checkout_but_rejects_wrong_checkout(tmp_path):
    pkg, smoke_dir = tmp_path / "package", tmp_path / "smoke"
    pkg.mkdir()
    smoke_dir.mkdir()
    head_sha = "a" * 40
    merge_sha = "c" * 40
    fixture = "b" * 64
    manifest = {"git_revision": merge_sha, "incident_id": "SAN-P1",
                "source_sha256": fixture,
                "runtime_execution_attested": False,
                "live_remediation_authorized": False}
    cockpit = {"incident_id": "SAN-P1", "source_sha256": fixture}
    smoke = {"incident_id": "SAN-P1", "source_sha256": fixture}
    provenance = {"run_id": "123", "commit_sha": merge_sha,
                  "pr_head_sha": head_sha}
    for directory, name, value in (
        (pkg, "manifest.json", manifest),
        (pkg, "cockpit.json", cockpit),
        (smoke_dir, "aiops2-packaged-demo-smoke.json", smoke),
        (smoke_dir, "aiops2-packaged-demo-smoke-provenance.json", provenance),
    ):
        (directory / name).write_text(json.dumps(value), encoding="utf-8")

    def check():
        return verify_bundle(pkg, smoke_dir, repository="alimtalbi-ata/aiops",
                             head_sha=head_sha, run_id="123", run_attempt="1")

    with patch("verify_aiops2_customer_demo_bundle.verify_package", return_value=True), \
         patch("verify_aiops2_customer_demo_bundle.verify_smoke", return_value=True):
        assert check()
        manifest["git_revision"] = head_sha
        (pkg / "manifest.json").write_text(json.dumps(manifest))
        assert not check()


def test_qualification_report_fails_closed_when_artifacts_are_missing(tmp_path):
    report = build_qualification_report(
        tmp_path / "missing-package", tmp_path / "missing-smoke",
        repository="alimtalbi-ata/aiops", head_sha="a" * 40,
        run_id="123", run_attempt="1")
    assert report["artifact_consistency"] == "BLOCKED"
    assert report["customer_demo_qualification"] == "BLOCKED"
    assert report["live_qualification"] == "NO_GO"
    for field in ("ci_run_verified", "browser_rehearsal_verified",
                  "runtime_attested", "independent_postcheck_verified",
                  "live_remediation_authorized"):
        assert report[field] is False


def test_qualification_report_does_not_promote_synthetic_pass_to_ci_or_live(tmp_path):
    with patch("verify_aiops2_customer_demo_bundle.verify_bundle", return_value=True):
        report = build_qualification_report(
            tmp_path / "package", tmp_path / "smoke",
            repository="alimtalbi-ata/aiops", head_sha="a" * 40,
            run_id="123", run_attempt="1")
    assert report["artifact_consistency"] == "PASS"
    assert report["customer_demo_qualification"] == "PENDING_INDEPENDENT_CI_AND_BROWSER_REVIEW"
    assert report["live_qualification"] == "NO_GO"
    assert report["ci_run_verified"] is False
    assert report["browser_rehearsal_verified"] is False
    assert report["runtime_attested"] is False
    assert report["trust_boundary"].startswith("UNSIGNED_LOCAL_REPORT")
