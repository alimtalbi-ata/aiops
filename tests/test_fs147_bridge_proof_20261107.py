"""Strict FS147 bridge proof gate tests: fixtures only, no Debian calls."""
from copy import deepcopy
import pytest
from worker.fs147_bridge_proof import attest_bridge_measurement


def sample():
    return {
        "source": "fs-lab-bridge-readonly", "filesystem": "/fs-lab",
        "read_only": True, "commands": ["df", "du", "ls"],
        "used_percent": 92, "collected_at": "2026-11-07T05:00:00+00:00",
        "command_results": {
            "df": {"exit_code": 0, "stdout": "Filesystem /fs-lab 92%", "stderr": ""},
            "du": {"exit_code": 0, "stdout": "11264 /fs-lab", "stderr": ""},
            "ls": {"exit_code": 0, "stdout": "aiops2-demo-fill.bin", "stderr": ""},
        },
    }


def test_valid_structured_proof():
    assert len(attest_bridge_measurement(sample())) == 3


@pytest.mark.parametrize("mutate", [
    lambda x: x.pop("command_results"),
    lambda x: x["command_results"].pop("du"),
    lambda x: x["command_results"]["df"].update(exit_code=1),
    lambda x: x["command_results"]["ls"].update(stdout=""),
    lambda x: x["command_results"]["du"].update(stdout="somewhere else"),
    lambda x: x.update(read_only=False),
    lambda x: x.update(commands=["df", "du", "ls", "rm"]),
    lambda x: x.update(used_percent=float("nan")),
    lambda x: x.update(collected_at="2026-11-07T05:00:00"),
    lambda x: x["command_results"]["df"].update(stderr="permission denied"),
])
def test_incomplete_or_untrusted_proof_rejected(mutate):
    value = deepcopy(sample())
    mutate(value)
    with pytest.raises(ValueError):
        attest_bridge_measurement(value)
