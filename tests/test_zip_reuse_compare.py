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
