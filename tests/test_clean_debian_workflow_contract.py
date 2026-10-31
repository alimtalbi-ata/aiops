"""Static security contract for the clean-host deployment workflow."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/deploy-clean-debian.yml").read_text()
DOCS = (ROOT / "docs/operations/APPROVED-CLEAN-DEBIAN-DEPLOYMENT.md").read_text()


class CleanDebianWorkflowContractTests(unittest.TestCase):
    def test_dispatch_requires_exact_commit_sha_not_movable_ref(self):
        self.assertIn("source_sha:", WORKFLOW)
        self.assertIn('[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]', WORKFLOW)
        self.assertNotIn("source_ref:", WORKFLOW)
        self.assertIn("ref: ${{ inputs.source_sha }}", WORKFLOW)
        self.assertIn("checkout_sha_mismatch", WORKFLOW)

    def test_exact_head_ci_and_approved_ancestry_are_required(self):
        self.assertIn("APPROVED_SOURCE_ANCESTRY=PASS", WORKFLOW)
        self.assertIn("EXACT_HEAD_CI=PASS", WORKFLOW)
        self.assertIn(".github/workflows/quality.yml", WORKFLOW)
        self.assertIn(".github/workflows/debian12-qualification.yml", WORKFLOW)
        self.assertIn("actions: read", WORKFLOW)

    def test_target_path_is_restricted_to_dedicated_aiops_directory(self):
        self.assertIn("^/home/aiops/aiops2-clean-[A-Za-z0-9_-]+$", WORKFLOW)

    def test_remote_preflight_requires_aiops_and_no_existing_stack(self):
        self.assertIn('[[ "$(id -un)" == "aiops" ]]', WORKFLOW)
        self.assertIn("existing_aiops2_containers_on_target", WORKFLOW)
        self.assertIn("existing_aiops2_volumes_on_target", WORKFLOW)
        self.assertIn("existing_aiops2_networks_on_target", WORKFLOW)

    def test_documentation_describes_automated_gates(self):
        self.assertIn("exact-head", DOCS)
        self.assertIn("aiops2-clean-", DOCS)
        self.assertIn("AIOps2-prefixed containers, volumes or networks", DOCS)
        self.assertIn("CI-gated first-install path", DOCS)


if __name__ == "__main__":
    unittest.main()
