"""Offline regression: Docker running != Portal readiness without health evidence.

No Docker host is contacted. Debian E2E remains NOT_VERIFIED.
"""
import importlib.util
import json
from pathlib import Path
from unittest import TestCase, main, mock

SOURCE = Path(__file__).resolve().parents[2] / "scripts/ops/live_usecase_qualification.py"
spec = importlib.util.spec_from_file_location("live_usecase_qualification", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PortalReadinessContract(TestCase):
    def probe(self, state):
        response = mock.Mock(returncode=0, stdout=json.dumps(state))
        with mock.patch.object(module.subprocess, "run", return_value=response) as runner:
            result = module.portal_probe()
        runner.assert_called_once()
        self.assertEqual(runner.call_args.args[0][:2], ["docker", "inspect"])
        return result

    def test_running_without_healthcheck_is_unverified(self):
        result = self.probe({"Status": "running"})
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertEqual(result["reason"], "NO_HEALTH_EVIDENCE")

    def test_starting_is_unverified(self):
        result = self.probe({"Status": "running", "Health": {"Status": "starting"}})
        self.assertEqual(result["status"], "UNVERIFIED")

    def test_unhealthy_is_hold(self):
        self.assertEqual(self.probe({"Status": "running", "Health": {"Status": "unhealthy"}})["status"], "HOLD")

    def test_exited_is_hold_even_if_health_says_healthy(self):
        self.assertEqual(self.probe({"Status": "exited", "Health": {"Status": "healthy"}})["status"], "HOLD")

    def test_running_healthy_passes_container_probe_only(self):
        self.assertEqual(self.probe({"Status": "running", "Health": {"Status": "healthy"}})["status"], "PASS")

    def test_missing_docker_inspection_is_unverified(self):
        with mock.patch.object(module.subprocess, "run", return_value=mock.Mock(returncode=1, stdout="")):
            self.assertEqual(module.portal_probe()["status"], "UNVERIFIED")


if __name__ == "__main__":
    main()
