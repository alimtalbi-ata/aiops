"""Negative tests for the strict Temporal start history decoder."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.temporal_start_history import decode_initial_start_args

ARGS = {"run_id": "run-01", "mode": "DEMO", "scenario_id": "acme", "version": 0}


def history(value=ARGS, *, event_type=1, event_id=1, encoding=b"json/plain", payload_count=1):
    payload = NS(metadata={"encoding": encoding}, data=json.dumps(value).encode())
    event = NS(event_type=event_type, event_id=event_id,
               workflow_execution_started_event_attributes=NS(
                   input=NS(payloads=[payload] * payload_count)))
    return [event]


def test_only_exact_initial_start_payload_is_decoded():
    assert decode_initial_start_args(history()) == ARGS


def test_missing_wrong_event_or_multiple_payloads_fail_closed():
    assert decode_initial_start_args([]) is None
    assert decode_initial_start_args(history(event_type=2)) is None
    assert decode_initial_start_args(history(event_id=2)) is None
    assert decode_initial_start_args(history(payload_count=2)) is None
    assert decode_initial_start_args(history(payload_count=0)) is None
    assert decode_initial_start_args(history(encoding=b"binary/plain")) is None
    assert decode_initial_start_args(history(dict(ARGS, version=True))) is None
    assert decode_initial_start_args(history(dict(ARGS, extra="forged"))) is None


def test_duplicate_json_keys_are_rejected():
    event = history()[0]
    event.workflow_execution_started_event_attributes.input.payloads[0].data = (
        b'{"run_id":"run-01","run_id":"forged","mode":"DEMO",'
        b'"scenario_id":"acme","version":0}'
    )
    assert decode_initial_start_args([event]) is None
