"""Evidence package is reproducible, offline, and detects tampering."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from package_aiops2_demo_evidence import create_package, verify_package


def test_package_is_deterministic_and_verifiable(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    m1 = create_package(first, revision="ci-fixed-revision")
    m2 = create_package(second, revision="ci-fixed-revision")
    assert m1 == m2
    assert verify_package(first)
    assert verify_package(second)
    assert m1["runtime_execution_attested"] is False
    assert m1["live_remediation_authorized"] is False
    for filename in ("cockpit.json", "cockpit.html", "acceptance.json", "manifest.json"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_modified_cockpit_fails_manifest_verification(tmp_path):
    directory = tmp_path / "package"
    create_package(directory, revision="test")
    with (directory / "cockpit.json").open("ab") as stream:
        stream.write(b"\nFORGED")
    assert verify_package(directory) is False


def test_manifest_cannot_claim_real_execution(tmp_path):
    directory = tmp_path / "package"
    create_package(directory, revision="test")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["runtime_execution_attested"] = True
    manifest_path.write_text(json.dumps(manifest))
    assert verify_package(directory) is False


def test_package_does_not_overwrite_existing_evidence(tmp_path):
    directory = tmp_path / "package"
    directory.mkdir()
    (directory / "operator-notes.txt").write_text("preserve")
    with pytest.raises(ValueError, match="empty"):
        create_package(directory, revision="test")
    assert (directory / "operator-notes.txt").read_text() == "preserve"
