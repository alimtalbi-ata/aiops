"""Decode only the initial Temporal WorkflowExecutionStarted JSON payload.

Requires an authenticated Temporal history response supplied by the caller.
A decoded payload is evidence of the stored start request, not evidence of
successful execution, Core ownership, or authorization.
"""
import json
from shared.temporal_start_fingerprint import canonical_start_request

# Temporal protobuf enum value for EVENT_TYPE_WORKFLOW_EXECUTION_STARTED.
START_EVENT_TYPE = 1


def decode_initial_start_args(events):
    """Return the exact four-field tuple or None on any ambiguity."""
    try:
        if not events or events[0].event_type != START_EVENT_TYPE:
            return None
        event = events[0]
        if event.event_id != 1:
            return None
        attrs = event.workflow_execution_started_event_attributes
        payloads = attrs.input.payloads
        if len(payloads) != 1:
            return None
        payload = payloads[0]
        if payload.metadata.get("encoding") != b"json/plain":
            return None
        if not isinstance(payload.data, bytes) or len(payload.data) > 8192:
            return None
        # Reject duplicate JSON keys rather than accepting the last value.
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate JSON key")
                value[key] = item
            return value
        value = json.loads(payload.data.decode("utf-8"),
                           object_pairs_hook=unique_object)
        if not isinstance(value, dict) or set(value) != {
            "run_id", "mode", "scenario_id", "version"
        }:
            return None
        canonical_start_request(**value)
        return value
    except (AttributeError, KeyError, TypeError, ValueError, UnicodeError):
        return None
