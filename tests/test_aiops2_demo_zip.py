"""Downloaded CI demo ZIP must be canonical and cannot smuggle extra entries."""
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from package_aiops2_demo_evidence import create_package
from verify_aiops2_demo_zip import verify_zip


def make_zip(folder, destination):
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.iterdir()):
            archive.write(path, path.name)


def test_downloaded_demo_zip_is_canonical(tmp_path):
    folder = tmp_path / "demo"
    create_package(folder, revision="synthetic-ci")
    destination = tmp_path / "demo.zip"
    make_zip(folder, destination)
    assert verify_zip(destination) is True


def test_extra_zip_entry_is_rejected(tmp_path):
    folder = tmp_path / "demo"
    create_package(folder, revision="synthetic-ci")
    destination = tmp_path / "demo.zip"
    make_zip(folder, destination)
    with zipfile.ZipFile(destination, "a") as archive:
        archive.writestr("production-proof.json", '{"verified":true}')
    assert verify_zip(destination) is False


def test_zip_with_rehashed_forged_report_is_rejected(tmp_path):
    folder = tmp_path / "demo"
    create_package(folder, revision="synthetic-ci")
    report = folder / "acceptance.json"
    value = json.loads(report.read_text())
    value["real_recovery_verified"] = True
    report.write_text(json.dumps(value))
    import hashlib
    manifest = folder / "manifest.json"
    m = json.loads(manifest.read_text())
    m["files_sha256"]["acceptance.json"] = hashlib.sha256(
        report.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(m))
    destination = tmp_path / "demo.zip"
    make_zip(folder, destination)
    assert verify_zip(destination) is False
