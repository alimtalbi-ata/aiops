import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("aiops_release_verifier",ROOT/"tests"/"verify-package.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

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
        "synthetic_analyst_critic_quality="+("PASS" if qualified else "NOT_RUN"),
        "ci_evidence_carried="+("yes" if qualified else "no"),
        "real_model_qualification=NOT_RUN",
        "production_qualification=NOT_RUN",
    ]
    entries["RELEASE-MANIFEST.txt"]=("\n".join(flags)+"\n").encode()
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


if __name__=="__main__":
    unittest.main()
