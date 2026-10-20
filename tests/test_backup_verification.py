"""Offline backup preflight tests: no Docker, server access or real secrets."""
import hashlib
import importlib.util
import io
import json
import pathlib
import tarfile
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("aiops_backup_verifier",ROOT/"deploy"/"verify_backup.py")
CHECK=importlib.util.module_from_spec(spec)
spec.loader.exec_module(CHECK)


def synthetic_backup(folder,stack_id="aiops2-rebuild",malicious=False):
    names=[
        "aiops.dump","n8n.dump","temporal.dump","temporal_visibility.dump",
        "glpi-mariadb.sql","aiops2-n8n-data.tar.gz","aiops2-glpi-data.tar.gz",
        "aiops2-grafana-data.tar.gz","aiops2-prometheus-data.tar.gz",
        ".env.private","git-head.txt",
    ]
    folder.mkdir(parents=True,exist_ok=True)
    for filename in names:
        path=folder/filename
        if filename.endswith(".dump"):
            path.write_bytes(b"PGDMP"+b"synthetic-archive-fixture")
        elif filename.endswith(".tar.gz"):
            with tarfile.open(path,"w:gz") as tar:
                data=b"synthetic artifact"
                entry=tarfile.TarInfo("../../unsafe" if malicious and filename=="aiops2-n8n-data.tar.gz" else "./synthetic.txt")
                entry.size=len(data)
                tar.addfile(entry,io.BytesIO(data))
        elif filename=="glpi-mariadb.sql":
            path.write_text("-- synthetic GLPI fixture\nselect 1;\n",encoding="utf-8")
        elif filename==".env.private":
            path.write_text("DEMO_ONLY=not_a_real_secret\n",encoding="utf-8")
        else:
            path.write_text("synthetic-only\n",encoding="utf-8")
    manifest={"format_version":2,"stack_id":stack_id,"backup_status":"COMPLETE",
              "contains_secrets":True,"application_consistent":False,
              "files":names}
    (folder/"BACKUP-MANIFEST.json").write_text(json.dumps(manifest),encoding="utf-8")
    entries=[]
    for path in sorted(folder.iterdir()):
        if path.name=="SHA256SUMS":continue
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(digest+"  ./"+path.name)
    (folder/"SHA256SUMS").write_text("\n".join(entries)+"\n",encoding="utf-8")


class BackupVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.tmp.name)/"backup"
        synthetic_backup(self.root)
    def tearDown(self):self.tmp.cleanup()

    def test_valid_synthetic_backup_is_accepted_for_named_stack(self):
        result=CHECK.verify_backup(self.root,"aiops2-rebuild")
        self.assertEqual(result["result"],"PASS")
        self.assertEqual(result["stack_id"],"aiops2-rebuild")
        self.assertFalse(result["application_consistent"])

    def test_cross_stack_restore_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"stack_identity_mismatch"):
            CHECK.verify_backup(self.root,"aiops-v1")

    def test_modified_database_is_detected(self):
        with (self.root/"aiops.dump").open("ab") as f:f.write(b"tampered")
        with self.assertRaisesRegex(ValueError,"checksum_mismatch"):
            CHECK.verify_backup(self.root,"aiops2-rebuild")

    def test_incomplete_marker_fails_closed(self):
        (self.root/".BACKUP_INCOMPLETE").write_text("incomplete")
        with self.assertRaisesRegex(ValueError,"backup_incomplete"):
            CHECK.verify_backup(self.root,"aiops2-rebuild")

    def test_unsafe_archive_member_is_rejected(self):
        synthetic_backup(self.root,malicious=True)
        with self.assertRaisesRegex(ValueError,"unsafe_tar_member"):
            CHECK.verify_backup(self.root,"aiops2-rebuild")

    def test_checksum_valid_symlink_member_is_rejected(self):
        filename="aiops2-n8n-data.tar.gz"
        with tarfile.open(self.root/filename,"w:gz") as tar:
            member=tarfile.TarInfo("./link")
            member.type=tarfile.SYMTYPE
            member.linkname="safe-looking-target"
            tar.addfile(member)
        self._rebuild_checksums()
        with self.assertRaisesRegex(ValueError,"backup_tar_special_member_forbidden"):
            CHECK.verify_backup(self.root,"aiops2-rebuild")

    def test_checksum_valid_device_member_is_rejected(self):
        filename="aiops2-glpi-data.tar.gz"
        with tarfile.open(self.root/filename,"w:gz") as tar:
            member=tarfile.TarInfo("./unsafe-device")
            member.type=tarfile.CHRTYPE
            tar.addfile(member)
        self._rebuild_checksums()
        with self.assertRaisesRegex(ValueError,"backup_tar_special_member_forbidden"):
            CHECK.verify_backup(self.root,"aiops2-rebuild")

    def _rebuild_checksums(self):
        entries=[]
        for path in sorted(self.root.iterdir()):
            if path.name=="SHA256SUMS":
                continue
            entries.append(hashlib.sha256(path.read_bytes()).hexdigest()+"  ./"+path.name)
        (self.root/"SHA256SUMS").write_text("\n".join(entries)+"\n",encoding="utf-8")

    def test_redirected_backup_file_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            target=pathlib.Path(external)/"fake.dump"
            target.write_bytes((self.root/"aiops.dump").read_bytes())
            (self.root/"aiops.dump").unlink()
            (self.root/"aiops.dump").symlink_to(target)
            with self.assertRaisesRegex(ValueError,"backup_symlink_file_forbidden"):
                CHECK.verify_backup(self.root,"aiops2-rebuild")

    def test_checksum_manifest_extraneous_file_is_rejected(self):
        (self.root/"unexpected-secret.txt").write_text("synthetic test only")
        self._rebuild_checksums()
        with self.assertRaisesRegex(ValueError,"checksum_manifest_coverage_incomplete"):
            CHECK.verify_backup(self.root,"aiops2-rebuild")

    def test_missing_temporal_visibility_dump_is_rejected(self):
        (self.root/"temporal_visibility.dump").unlink()
        with self.assertRaisesRegex(ValueError,"missing_or_empty"):
            CHECK.verify_backup(self.root,"aiops2-rebuild")

if __name__=="__main__":unittest.main()
