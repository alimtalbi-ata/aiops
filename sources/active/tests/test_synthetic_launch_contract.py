
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SyntheticLaunchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = (
            ROOT / "app/core/main.py"
        ).read_text()
        cls.worker = (
            ROOT / "app/worker/main.py"
        ).read_text()
        cls.simulator = (
            ROOT / "app/simulator/main.py"
        ).read_text()

    def test_python_syntax(self):
        for name, source in (
            ("core", self.core),
            ("worker", self.worker),
            ("simulator", self.simulator),
        ):
            with self.subTest(name=name):
                ast.parse(source)

    def test_core_transactional_launch(self):
        self.assertIn(
            'pg_advisory_xact_lock',
            self.core,
        )
        self.assertIn(
            'incident_idempotency_conflict',
            self.core,
        )
        self.assertIn(
            'scenario_not_synthetic',
            self.core,
        )

    def test_worker_uses_atomic_core_endpoint(self):
        self.assertIn(
            '"/api/synthetic/launch"',
            self.worker,
        )
        self.assertIn(
            'execution_state_conflict',
            self.worker,
        )

    def test_simulator_cannot_launch_live(self):
        self.assertIn(
            "simulator cannot launch LIVE",
            self.simulator,
        )

    def test_simulator_uses_worker(self):
        self.assertIn(
            "http://aiops2-worker:815",
            self.simulator,
        )


if __name__ == "__main__":
    unittest.main()
