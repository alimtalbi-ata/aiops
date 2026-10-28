"""Offline contract: rollback container names must be valid, unique and reversible.

Never executes the deployment script or Docker. Runtime rollback remains NOT_TESTED.
"""
import re
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/deploy-demo-studio-v2.sh"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,254}\\Z")


def valid_docker_name(name):
    return bool(NAME.fullmatch(name))


def backup_expression():
    assignments = [line.split("=", 1)[1] for line in SCRIPT.read_text().splitlines()
                   if line.startswith("BACKUP=")]
    if len(assignments) != 1:
        raise AssertionError("expected exactly one BACKUP assignment")
    return assignments[0]


def evaluate_backup():
    # Evaluate ONLY the extracted assignment, never source the deployment script.
    expression = backup_expression()
    result = subprocess.run(
        ["bash", "-c", "set -euo pipefail\\nBACKUP=" + expression +
         "\\nprintf '%s' \\"$BACKUP\\""],
        check=True, text=True, capture_output=True, timeout=5,
    )
    return result.stdout


class StableRollbackNameContract(unittest.TestCase):
    def test_backup_name_valid_for_docker(self):
        name = evaluate_backup()
        self.assertTrue(valid_docker_name(name), repr(name))
        self.assertTrue(name.startswith("aiops2-portal-rollback-v2-"))
        self.assertNotEqual(name, "aiops2-rebuild-portal")

    def test_distinct_shells_get_distinct_names(self):
        self.assertNotEqual(evaluate_backup(), evaluate_backup())

    def test_literal_dollar_and_invalid_names_rejected(self):
        for value in ("rollback-$", "rollback name", "rollback/name",
                      "rollback:name", "", ".rollback", "a" * 256):
            with self.subTest(value=value):
                self.assertFalse(valid_docker_name(value))

    def test_same_backup_variable_used_for_switch_and_recovery(self):
        source = SCRIPT.read_text()
        self.assertIn('docker rename "$OLD" "$BACKUP"', source)
        self.assertIn('docker rename "$BACKUP" "$OLD"', source)
        self.assertIn('docker inspect "$BACKUP"', source)


if __name__ == "__main__":
    unittest.main()
