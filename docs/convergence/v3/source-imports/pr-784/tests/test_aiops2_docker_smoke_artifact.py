"""Offline Docker smoke artifact provenance validation regression tests."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_aiops2_docker_smoke_artifact import verify

HEAD = "a" * 40
SMOKE = {
    "schema": "aiops2.packaged-demo-smoke.v1",
    "accepted": True,
    "scope": "LOCAL_SYNTHETIC_ONLY",
    "runtime_attested": False,
    "live_actions_authorized": False,
    "incident_id": "ACME-SAN-P1",
    "source_sha256": "b" * 64,
}
PROVENANCE = {
    "schema": "aiops2.github-actions-smoke-provenance.v1",
    "repository": "alimtalbi-ata/aiops",
    "commit_sha": HEAD,
    "pr_head_sha": HEAD,
    "ref": "refs/heads/integration/aiops2-convergence-20261114",
    "run_id": "12345",
    "run_attempt": "1",
    "workflow": "AIOps quality gates",
    "event_name": "push",
    "trust_boundary": "UNSIGNED_GITHUB_ACTIONS_RUN_METADATA_NOT_RUNTIME_ATTESTATION",
}


def check(smoke=SMOKE, provenance=PROVENANCE, *, head=HEAD):
    return verify(smoke, provenance, repository="alimtalbi-ata/aiops",
                  head_sha=head, run_id="12345", run_attempt="1")


def test_valid_synthetic_pair_only():
    assert check()


def test_reject_positive_runtime_claim():
    altered = dict(SMOKE, runtime_attested=True)
    assert not check(smoke=altered)


def test_reject_live_authorization():
    altered = dict(SMOKE, live_actions_authorized=True)
    assert not check(smoke=altered)


def test_reject_wrong_run_or_revision():
    assert not check(provenance=dict(PROVENANCE, run_id="999"))
    assert not check(provenance=dict(PROVENANCE, pr_head_sha="c" * 40))


def test_reject_push_checkout_not_equal_to_head():
    assert not check(provenance=dict(PROVENANCE, commit_sha="c" * 40))


def test_pr_merge_checkout_can_differ_from_head():
    altered = dict(PROVENANCE, event_name="pull_request",
                   ref="refs/pull/713/merge", commit_sha="c" * 40)
    assert check(provenance=altered)


def test_reject_extra_field_and_invalid_sha():
    assert not check(smoke=dict(SMOKE, fake_real_proof=True))
    assert not check(smoke=dict(SMOKE, source_sha256="not-a-digest"))


def test_reject_missing_or_nonobject():
    assert not check(smoke=[])
    assert not check(provenance=None)


def test_scheduled_workflow_uses_same_checkout_as_head():
    assert check(provenance=dict(PROVENANCE, event_name="schedule", ref="refs/heads/main"))
    assert not check(provenance=dict(PROVENANCE, event_name="schedule",
                                     ref="refs/heads/main", commit_sha="c" * 40))


def test_reject_pr_event_with_non_pr_ref():
    assert not check(provenance=dict(PROVENANCE, event_name="pull_request",
                                     ref="refs/heads/main", commit_sha="c" * 40))
    assert not check(provenance=dict(PROVENANCE, event_name="pull_request",
                                     ref="refs/pull/713/head", commit_sha="c" * 40))


def test_reject_push_with_pr_ref():
    assert not check(provenance=dict(PROVENANCE, ref="refs/pull/713/merge"))


def test_tag_ref_for_manual_run_is_allowed_with_matching_sha():
    assert check(provenance=dict(PROVENANCE, event_name="workflow_dispatch",
                                 ref="refs/tags/v1.0"))
    assert not check(provenance=dict(PROVENANCE, event_name="workflow_dispatch",
                                     ref="refs/tags/v1.0", commit_sha="c" * 40))


def test_schedule_must_reference_branch():
    assert not check(provenance=dict(PROVENANCE, event_name="schedule",
                                     ref="refs/tags/v1.0"))


def test_offline_cli_accepts_matching_artifact(tmp_path):
    (tmp_path / "aiops2-packaged-demo-smoke.json").write_text(json.dumps(SMOKE))
    (tmp_path / "aiops2-packaged-demo-smoke-provenance.json").write_text(
        json.dumps(PROVENANCE))
    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_aiops2_docker_smoke_artifact.py"
    command = [sys.executable, str(script), str(tmp_path),
               "--repository", "alimtalbi-ata/aiops", "--head-sha", HEAD,
               "--run-id", "12345", "--run-attempt", "1"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "runtime NOT attested" in result.stdout
    altered = dict(PROVENANCE, run_id="999")
    (tmp_path / "aiops2-packaged-demo-smoke-provenance.json").write_text(
        json.dumps(altered))
    rejected = subprocess.run(command, capture_output=True, text=True, check=False)
    assert rejected.returncode == 1
    assert "BLOCKED" in rejected.stderr


def test_offline_cli_rejects_missing_and_malformed_files(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_aiops2_docker_smoke_artifact.py"
    command = [sys.executable, str(script), str(tmp_path),
               "--repository", "alimtalbi-ata/aiops", "--head-sha", HEAD,
               "--run-id", "12345", "--run-attempt", "1"]
    missing = subprocess.run(command, capture_output=True, text=True, check=False)
    assert missing.returncode == 1
    assert "BLOCKED" in missing.stderr
    (tmp_path / "aiops2-packaged-demo-smoke.json").write_text("{malformed")
    (tmp_path / "aiops2-packaged-demo-smoke-provenance.json").write_text(
        json.dumps(PROVENANCE))
    malformed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert malformed.returncode == 1
    assert "BLOCKED" in malformed.stderr


def test_reject_malformed_provenance_and_smoke_types():
    assert not check(smoke=dict(SMOKE, accepted="true"))
    assert not check(smoke=dict(SMOKE, live_actions_authorized="false"))
    assert not check(provenance=dict(PROVENANCE, event_name=[]))
    assert not check(provenance=dict(PROVENANCE, ref=[]))
    assert not check(provenance=dict(PROVENANCE, commit_sha=None))
    assert not check(provenance=dict(PROVENANCE, run_attempt=1))
    assert not check(provenance=dict(PROVENANCE, run_id="0"))
    assert not check(provenance=dict(PROVENANCE, run_attempt="0"))
