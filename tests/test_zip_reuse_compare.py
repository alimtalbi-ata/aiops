"""Synthetic offline qualification: never connects to production or GitHub."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recovery.tools.zip_reuse_compare import compare_inventory, index_checkout, main


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def row(name, content, **changes):
    base = {"archive": "SYNTHETIC-V2.13.4.zip", "archive_sha256": sha("archive"),
            "member_path": name, "member_sha256": sha(content),
            "sensitive_pattern_detected": False, "python_syntax": "parse_pass_not_completeness"}
    base.update(changes)
    return base


def inventory(*rows):
    return {"schema": "aiops-zip-source-inventory/v1", "member_count": len(rows), "members": list(rows)}


def nested_row(name, content, **changes):
    result = row(name, content)
    result.update({
        "nested_archive_member": "backup/hybrid.zip",
        "nested_archive_sha256": sha("nested-archive"),
        "reuse_status": "quarantine_review_required",
        "import_authorized": False,
    })
    result.update(changes)
    return result


def with_nested(*rows, outer=()):
    report = inventory(*outer)
    report.update({
        "nested_inspection_requested": True,
        "nested_member_count": len(rows),
        "nested_members": list(rows),
    })
    return report


class CompareTests(unittest.TestCase):
    def test_exact_path_duplicate_never_imports(self):
        r = compare_inventory(inventory(row("demo/replay.py", "pass\n")), {"demo/replay.py": sha("pass\n")})
        self.assertEqual(r["entries"][0]["status"], "EXACT_PATH_DUPLICATE")
        self.assertFalse(r["import_authorized"])
        self.assertFalse(r["complete_source_attested"])

    def test_exact_bytes_other_path_deduplicates(self):
        r = compare_inventory(inventory(row("legacy/old.py", "x=1\n")), {"demo/new.py": sha("x=1\n")})
        self.assertEqual(r["entries"][0]["status"], "EXACT_BYTES_OTHER_PATH")
        self.assertEqual(r["entries"][0]["matching_checkout_paths"], ["demo/new.py"])

    def test_divergent_same_path_needs_review(self):
        r = compare_inventory(inventory(row("demo/replay.py", "x=1")), {"demo/replay.py": sha("x=2")})
        self.assertEqual(r["entries"][0]["status"], "DIVERGENT_PATH_REVIEW")

    def test_new_candidate_requires_review(self):
        r = compare_inventory(inventory(row("demo/replay.py", "x=1")), {})
        self.assertEqual(r["entries"][0]["status"], "NEW_CANDIDATE_REVIEW")

    def test_sensitive_or_broken_source_blocked_even_if_duplicate(self):
        for changes in ({"sensitive_pattern_detected": True}, {"python_syntax": "parse_failed"}):
            with self.subTest(changes=changes):
                r = compare_inventory(inventory(row("safe.py", "x=1", **changes)), {"safe.py": sha("x=1")})
                self.assertEqual(r["entries"][0]["status"], "BLOCKED_REVIEW")

    def test_unknown_sensitive_status_is_blocked(self):
        r = compare_inventory(inventory(row("safe.py", "x=1", sensitive_pattern_detected=None)), {})
        self.assertEqual(r["entries"][0]["status"], "BLOCKED_REVIEW")

    def test_nested_source_exact_bytes_and_path_divergence(self):
        source = with_nested(
            nested_row("tools/replay.py", "pass\n"),
            nested_row("legacy/renamed.py", "x=1\n"),
            nested_row("tools/changed.py", "old\n"),
            nested_row("tools/unknown.py", "unknown\n"),
        )
        checkout = {
            "tools/replay.py": sha("pass\n"),
            "current/replay.py": sha("x=1\n"),
            "tools/changed.py": sha("new\n"),
        }
        result = compare_inventory(source, checkout)
        self.assertEqual(result["entry_count"], 4)
        self.assertEqual(result["nested_entry_count"], 4)
        statuses = {entry["member_path"]: entry["status"] for entry in result["entries"]}
        self.assertEqual(statuses, {
            "tools/replay.py": "EXACT_PATH_DUPLICATE",
            "legacy/renamed.py": "EXACT_BYTES_OTHER_PATH",
            "tools/changed.py": "DIVERGENT_PATH_REVIEW",
            "tools/unknown.py": "NEW_CANDIDATE_REVIEW",
        })
        self.assertTrue(all(entry["origin_kind"] == "nested" for entry in result["entries"]))
        self.assertTrue(all(entry["nested_archive_sha256"] == sha("nested-archive")
                            for entry in result["entries"]))
        self.assertTrue(all(entry["import_authorized"] is False for entry in result["entries"]))

    def test_nested_and_outer_same_relative_path_are_independent(self):
        source = with_nested(nested_row("tools/replay.py", "new\n"),
                             outer=(row("tools/replay.py", "old\n"),))
        result = compare_inventory(source, {"tools/replay.py": sha("old\n")})
        self.assertEqual(result["entry_count"], 2)
        self.assertEqual([x["origin_kind"] for x in result["entries"]], ["outer", "nested"])
        self.assertEqual([x["status"] for x in result["entries"]],
                         ["EXACT_PATH_DUPLICATE", "DIVERGENT_PATH_REVIEW"])

    def test_nested_sensitive_source_never_marked_reusable(self):
        result = compare_inventory(
            with_nested(nested_row("tools/safe.py", "pass\n",
                                   sensitive_pattern_detected=True)),
            {"tools/safe.py": sha("pass\n")})
        self.assertEqual(result["entries"][0]["status"], "BLOCKED_REVIEW")
        self.assertEqual(result["entries"][0]["matching_checkout_paths"], [])

    def test_nested_provenance_must_be_complete_and_quarantined(self):
        invalid = [
            {"nested_archive_sha256": "bad"},
            {"nested_archive_member": "../escape.zip"},
            {"nested_archive_member": "not-an-archive.py"},
            {"import_authorized": True},
            {"reuse_status": "approved"},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                compare_inventory(with_nested(nested_row("safe.py", "pass\n", **changes)), {})
        with self.assertRaises(ValueError):
            compare_inventory(with_nested(nested_row("safe.py", "pass\n"),
                                          nested_row("safe.py", "pass\n")), {})
        for change in ({"nested_member_count": 2}, {"nested_inspection_requested": False}):
            doc = with_nested(nested_row("safe.py", "pass\n"))
            doc.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                compare_inventory(doc, {})

    def test_nested_zip_to_checkout_end_to_end_synthetic(self):
        import io
        import zipfile
        from recovery.tools.zip_source_recovery import inventory as inspect_zip
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "AIOPS-V2.13.4-SYNTHETIC.zip"
            inner = io.BytesIO()
            with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("tools/replay.py", "pass\n")
                z.writestr("03_HLD_Architecture_Logique.pdf", b"%PDF-1.7 synthetic")
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("backup/hybrid.zip", inner.getvalue())
            checkout = root / "checkout"
            (checkout / "tools").mkdir(parents=True)
            (checkout / "tools" / "replay.py").write_text("pass\n")
            source = inspect_zip([archive], inspect_nested=True)
            report = compare_inventory(source, index_checkout(checkout))
            self.assertEqual(source["nested_member_count"], 1)
            self.assertEqual(source["nested_asset_count"], 1)
            self.assertEqual(report["nested_entry_count"], 1)
            self.assertEqual(report["entries"][0]["status"], "EXACT_PATH_DUPLICATE")
            self.assertEqual(report["entries"][0]["nested_archive_sha256"],
                             hashlib.sha256(inner.getvalue()).hexdigest())
            self.assertFalse(report["import_authorized"])
            self.assertEqual(sorted(p.name for p in checkout.rglob("*") if p.is_file()), ["replay.py"])

    def test_invalid_inventory_fails_closed(self):
        cases = [inventory(row("../escape.py", "x")), inventory(row("a.py", "x", member_sha256="not-sha")),
                 inventory(row("a.py", "x"), row("a.py", "x")),
                 {"schema": "wrong", "members": [], "member_count": 0},
                 {"schema": "aiops-zip-source-inventory/v1", "members": [], "member_count": 4}]
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ValueError):
                compare_inventory(item, {})

    def test_checkout_index_does_not_follow_symlinks_or_secret_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"; root.mkdir()
            (root / "demo").mkdir(); (root / "demo" / "safe.py").write_text("x=1\n")
            (root / "demo" / "link.py").symlink_to(root / "demo" / "safe.py")
            (root / ".git").mkdir(); (root / ".git" / "config.py").write_text("x=2")
            (root / "tokens.json").write_text("{}")
            (root / "outside").symlink_to(Path(td), target_is_directory=True)
            self.assertEqual(index_checkout(root), {"demo/safe.py": sha("x=1\n")})

    def test_non_directory_checkout_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "link").symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                index_checkout(root / "link")

    def test_cli_create_only_metadata_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"; repo.mkdir()
            (repo / "same.py").write_text("pass\n")
            src = root / "inventory.json"; src.write_text(json.dumps(inventory(row("same.py", "pass\n"))))
            out = root / "comparison.json"
            import sys
            with patch.object(sys, "argv", ["zip_reuse_compare", str(src), "--checkout", str(repo), "--output", str(out)]):
                main()
            self.assertEqual(json.loads(out.read_text())["entries"][0]["status"], "EXACT_PATH_DUPLICATE")
            with patch.object(sys, "argv", ["zip_reuse_compare", str(src), "--checkout", str(repo), "--output", str(out)]):
                with self.assertRaises(FileExistsError):
                    main()


if __name__ == "__main__":
    unittest.main()
