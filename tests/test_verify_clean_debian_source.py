import unittest

from scripts.verify_clean_debian_source import verify_source


REPO = "alimtalbi-ata/aiops"
SHA = "a" * 40


def run(name, path, sha=SHA, status="completed", conclusion="success", repo=REPO, created="2026-10-31T20:00:00Z"):
    return {
        "name": name,
        "path": path,
        "head_sha": sha,
        "head_repository": {"full_name": repo},
        "status": status,
        "conclusion": conclusion,
        "created_at": created,
        "run_attempt": 1,
    }


class VerifyCleanDebianSourceTests(unittest.TestCase):
    def fixture(self, comparison="ahead", runs=None):
        responses = {
            "/compare/" + SHA + "...main": {"status": comparison},
            "/actions/runs?head_sha=" + SHA + "&per_page=100": {
                "workflow_runs": runs if runs is not None else [
                    run("AIOps quality gates", ".github/workflows/quality.yml"),
                    run("Debian 12 and 13 installation and runtime qualification",
                        ".github/workflows/debian12-qualification.yml"),
                ]
            },
        }
        calls = []

        def get_json(repo, token, path):
            calls.append((repo, token, path))
            return responses[path]

        return get_json, calls

    def test_accepts_main_ancestor_with_both_exact_head_gates_green(self):
        get_json, calls = self.fixture()
        result = verify_source(REPO, SHA, "read-only-token", get_json)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(calls), 2)

    def test_rejects_source_not_in_main(self):
        get_json, _ = self.fixture(comparison="behind")
        with self.assertRaisesRegex(ValueError, "not_ancestor_of_main"):
            verify_source(REPO, SHA, "read-only-token", get_json)

    def test_rejects_missing_exact_head_workflow(self):
        get_json, _ = self.fixture(runs=[
            run("AIOps quality gates", ".github/workflows/quality.yml")
        ])
        with self.assertRaisesRegex(ValueError, "missing_exact_head_ci"):
            verify_source(REPO, SHA, "read-only-token", get_json)

    def test_rejects_failed_or_in_progress_latest_run(self):
        get_json, _ = self.fixture(runs=[
            run("AIOps quality gates", ".github/workflows/quality.yml",
                conclusion="success"),
            run("AIOps quality gates", ".github/workflows/quality.yml",
                status="in_progress", conclusion=None, created="2026-10-31T20:01:00Z"),
            run("Debian 12 and 13 installation and runtime qualification",
                ".github/workflows/debian12-qualification.yml"),
        ])
        with self.assertRaisesRegex(ValueError, "exact_head_ci_not_success"):
            verify_source(REPO, SHA, "read-only-token", get_json)

    def test_rejects_fork_origin_even_when_workflow_names_match(self):
        get_json, _ = self.fixture(runs=[
            run("AIOps quality gates", ".github/workflows/quality.yml", repo="fork/aiops"),
            run("Debian 12 and 13 installation and runtime qualification",
                ".github/workflows/debian12-qualification.yml"),
        ])
        with self.assertRaisesRegex(ValueError, "missing_exact_head_ci"):
            verify_source(REPO, SHA, "read-only-token", get_json)

    def test_rejects_malformed_sha_and_missing_token(self):
        get_json, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, "full_40_character"):
            verify_source(REPO, "bad", "read-only-token", get_json)
        with self.assertRaisesRegex(ValueError, "token_missing"):
            verify_source(REPO, SHA, "", get_json)


if __name__ == "__main__":
    unittest.main()
