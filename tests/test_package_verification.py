import hashlib
import importlib.util
import json
import pathlib
import stat
import tempfile
import unittest
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("aiops_release_verifier",ROOT/"tests"/"verify-package.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REFRESH_SPEC=importlib.util.spec_from_file_location(
    "aiops_release_inventory",ROOT/"deploy"/"refresh_release_inventory.py")
REFRESH=importlib.util.module_from_spec(REFRESH_SPEC)
REFRESH_SPEC.loader.exec_module(REFRESH)

REQUIRED=(
    "compose.yml",
    "deploy/install.sh","deploy/migrate.sh","deploy/verify_backup.py",
    "deploy/package_tree.py","deploy/plan_isolation.py",
    "app/worker/workflow.py",
    "db/migrations/009_ai_decision_ledger.sql",
    "db/migrations/010_evidence_identity.sql",
    "tests/evidence-e2e.sh","tests/runtime-e2e.sh",
    "tests/model-evaluation-e2e.sh",
)


def fixture(tmp, *, qualified=False, failing_evidence=False, stale_reports=False):
    path=pathlib.Path(tmp)/"core.zip"
    entries={name:b"synthetic test source\n" for name in REQUIRED}
    status="CI-runtime-e2e-PASS" if qualified else "static-unit-only"
    flags=[
        "product=AIOps 2.0",
        "qualification="+status,
        "version=2.1.0-core-rc1.4",
        "synthetic_analyst_critic_quality="+("PASS" if qualified else "NOT_RUN"),
        "ci_evidence_carried="+("yes" if qualified else "no"),
        "real_model_qualification=NOT_RUN",
        "production_qualification=NOT_RUN",
    ]
    entries["RELEASE-MANIFEST.txt"]=("\n".join(flags)+"\n").encode()
    entries["manifests/MANIFEST.json"]=json.dumps({
        "release":"2.1.0-core-rc1.4",
        "files":[{"path":"compose.yml",
                  "bytes":len(entries["compose.yml"]),
                  "sha256":hashlib.sha256(entries["compose.yml"]).hexdigest()}]
    }).encode()
    if qualified or stale_reports:
        eval_result="FAIL" if failing_evidence else "PASS"
        entries["09-Qualification/ai-core-evaluation.json"]=json.dumps({
            "result":eval_result,
            "qualification_kind":"deterministic-integration-fixture",
            "ledger_persistence":{"status":"PASS"}
        }).encode()
        entries["09-Qualification/runtime-e2e-RUN.json"]=json.dumps({
            "result":"PASS","live_execution":"disabled"
        }).encode()
    entries["FILES-SHA256SUMS"]=("\n".join(
        hashlib.sha256(content).hexdigest()+"  ./"+name
        for name,content in sorted(entries.items())
    )+"\n").encode()
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name,payload in sorted(entries.items()):
            z.writestr(name,payload)
    path.with_suffix(".zip.sha256").write_text(
        hashlib.sha256(path.read_bytes()).hexdigest()+"  "+path.name+"\n"
    )
    return path


class ReleaseQualificationVerificationTests(unittest.TestCase):
    def test_unqualified_source_copy_has_explicit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=MODULE.verify(fixture(tmp))
            self.assertEqual(result["qualification"],"UNQUALIFIED_SOURCE_ONLY")
            self.assertEqual(result["status"],"PASS")

    def test_qualified_archive_requires_real_ci_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=MODULE.verify(fixture(tmp,qualified=True))
            self.assertEqual(result["qualification"],"SYNTHETIC_CI_PASS")

    def test_unqualified_zip_cannot_smuggle_old_ci_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"unqualified_source_cannot_carry_ci_reports"):
                MODULE.verify(fixture(tmp,stale_reports=True))

    def test_failed_model_evaluation_rejects_claimed_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"model_evaluation_ci_evidence_invalid"):
                MODULE.verify(fixture(tmp,qualified=True,failing_evidence=True))

    def test_tampering_with_outer_zip_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(tmp,qualified=True)
            path.write_bytes(path.read_bytes()+b"tampered")
            with self.assertRaisesRegex(ValueError,"outer_checksum_mismatch"):
                MODULE.verify(path)

    def test_missing_evaluation_record_rejects_ci_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(tmp,qualified=True)
            with zipfile.ZipFile(path) as source:
                entries={n:source.read(n) for n in source.namelist()
                         if n!="09-Qualification/ai-core-evaluation.json" and n!="FILES-SHA256SUMS"}
            entries["FILES-SHA256SUMS"]=("\n".join(
                hashlib.sha256(payload).hexdigest()+"  ./"+name
                for name,payload in sorted(entries.items())
            )+"\n").encode()
            with zipfile.ZipFile(path,"w") as z:
                for name,payload in entries.items():
                    z.writestr(name,payload)
            path.with_suffix(".zip.sha256").write_text(
                hashlib.sha256(path.read_bytes()).hexdigest()+"  "+path.name+"\n"
            )
            with self.assertRaisesRegex(ValueError,"qualified_release_missing_ci_evidence"):
                MODULE.verify(path)


    def test_symlink_archive_member_rejected_even_with_valid_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(tmp)
            with zipfile.ZipFile(path) as source:
                contents=[(info, source.read(info.filename)) for info in source.infolist()]
            with zipfile.ZipFile(path,"w") as target:
                for info,data in contents:
                    if info.filename=="compose.yml":
                        info.create_system=3
                        info.external_attr=(stat.S_IFLNK | 0o777)<<16
                    target.writestr(info,data)
            path.with_suffix(".zip.sha256").write_text(
                hashlib.sha256(path.read_bytes()).hexdigest()+"  "+path.name+"\n")
            with self.assertRaisesRegex(ValueError,"archive_symlink_forbidden"):
                MODULE.verify(path)

    def test_archive_expansion_ratio_rejected_even_with_valid_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(tmp)
            oversized=b"0"*(2*1024*1024)
            with zipfile.ZipFile(path) as source:
                entries={name:source.read(name) for name in source.namelist()
                         if name!="FILES-SHA256SUMS"}
            entries["docs/high-compression-fixture.txt"]=oversized
            entries["FILES-SHA256SUMS"]=("\n".join(
                hashlib.sha256(data).hexdigest()+"  ./"+name
                for name,data in sorted(entries.items())
            )+"\n").encode()
            with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as target:
                for name,data in entries.items():
                    target.writestr(name,data)
            path.with_suffix(".zip.sha256").write_text(
                hashlib.sha256(path.read_bytes()).hexdigest()+"  "+path.name+"\n")
            with self.assertRaisesRegex(ValueError,"archive_compression_ratio_limit_exceeded"):
                MODULE.verify(path)


    def test_stale_embedded_digest_rejected_even_if_outer_and_file_checksums_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(tmp)
            with zipfile.ZipFile(path) as source:
                entries={n:source.read(n) for n in source.namelist() if n!="FILES-SHA256SUMS"}
            embedded=json.loads(entries["manifests/MANIFEST.json"])
            embedded["files"][0]["sha256"]="0"*64
            entries["manifests/MANIFEST.json"]=json.dumps(embedded).encode()
            self._repack(path,entries)
            with self.assertRaisesRegex(ValueError,"embedded_manifest_sha_mismatch"):
                MODULE.verify(path)

    def test_stale_embedded_size_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(tmp)
            with zipfile.ZipFile(path) as source:
                entries={n:source.read(n) for n in source.namelist() if n!="FILES-SHA256SUMS"}
            embedded=json.loads(entries["manifests/MANIFEST.json"])
            embedded["files"][0]["bytes"]+=1
            entries["manifests/MANIFEST.json"]=json.dumps(embedded).encode()
            self._repack(path,entries)
            with self.assertRaisesRegex(ValueError,"embedded_manifest_size_mismatch"):
                MODULE.verify(path)

    def test_embedded_release_must_match_text_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(tmp)
            with zipfile.ZipFile(path) as source:
                entries={n:source.read(n) for n in source.namelist() if n!="FILES-SHA256SUMS"}
            embedded=json.loads(entries["manifests/MANIFEST.json"])
            embedded["release"]="8.0.0"
            entries["manifests/MANIFEST.json"]=json.dumps(embedded).encode()
            self._repack(path,entries)
            with self.assertRaisesRegex(ValueError,"embedded_release_version_mismatch"):
                MODULE.verify(path)

    def test_missing_embedded_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(tmp)
            with zipfile.ZipFile(path) as source:
                entries={n:source.read(n) for n in source.namelist()
                         if n not in ("FILES-SHA256SUMS","manifests/MANIFEST.json")}
            self._repack(path,entries)
            with self.assertRaisesRegex(ValueError,"required_files_missing"):
                MODULE.verify(path)

    def test_staged_inventory_refresh_reconciles_legacy_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            (root/"manifests").mkdir()
            (root/"compose.yml").write_text("new staged content\n")
            (root/"manifests/MANIFEST.json").write_text(json.dumps({
                "release":"8.0.0","name":"legacy",
                "files":[{"path":"compose.yml","bytes":0,"sha256":"0"*64}]
            }))
            self.assertEqual(REFRESH.refresh(root,"2.1.0-core-rc1.4"),1)
            doc=json.loads((root/"manifests/MANIFEST.json").read_text())
            self.assertEqual(doc["release"],"2.1.0-core-rc1.4")
            self.assertEqual(doc["source_manifest_release"],"8.0.0")
            self.assertEqual(doc["files"][0]["bytes"],len((root/"compose.yml").read_bytes()))
            self.assertEqual(doc["files"][0]["sha256"],
                             hashlib.sha256((root/"compose.yml").read_bytes()).hexdigest())

    @staticmethod
    def _repack(path,entries):
        entries["FILES-SHA256SUMS"]=("\n".join(
            hashlib.sha256(data).hexdigest()+"  ./"+name
            for name,data in sorted(entries.items())
        )+"\n").encode()
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as target:
            for name,data in sorted(entries.items()):
                target.writestr(name,data)
        path.with_suffix(".zip.sha256").write_text(
            hashlib.sha256(path.read_bytes()).hexdigest()+"  "+path.name+"\n"
        )


if __name__=="__main__":
    unittest.main()
