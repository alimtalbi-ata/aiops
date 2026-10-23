"""Offline V2.13.4 replay-to-STAR storyboard binding (no runtime I/O).

Bindings are operator-declared hints, never proof that a runtime checkpoint
occurred. The existing :17777 portal is not modified by this module.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from datetime import datetime
import re

from demo.star_legacy_replay_adapter import build_replay
from demo.star_portal_transport import export_storyboard
from demo.star_scene_scripts import scene_plan
from demo.star_snapshot_choreography import CUES

# A source family is only a plausible scene hint, not an attestation.
_ALLOWED_SOURCES = {
    "detect": frozenset({"events"}),
    "correlate": frozenset({"events", "stages"}),
    "enrich": frozenset({"stages"}),
    "analyze": frozenset({"analyses", "critiques"}),
    "ticket": frozenset({"stages"}),
    "approve": frozenset({"policy_decisions"}),
    "simulate": frozenset({"policy_decisions", "stages"}),
    "verify": frozenset({"stages"}),
    "close": frozenset({"stages"}),
}
_ALLOWED_BINDING_KEYS = frozenset({"source", "source_index"})


def bind_replay_to_transport(transport: Mapping, replay: Mapping,
                             bindings: Mapping) -> dict:
    """Attach declared replay references to nine existing read-only cues.

    Every bound source row must be unique and belong to the expected source
    family. Unbound cues remain explicitly unbound, never silently successful.
    """
    if not isinstance(transport, dict) or not isinstance(replay, dict) or not isinstance(bindings, dict):
        raise ValueError("transport, replay and bindings must be objects")
    if replay.get("schema") != "star-core-legacy-replay/v1" or replay.get("mode") != "DEMO":
        raise ValueError("unsupported replay schema/mode")
    if replay.get("status") not in {"BLOCKED", "RESOLVED"}:
        raise ValueError("unsupported replay status")
    if transport.get("schema") != "star-portal-transport-v1" or transport.get("run_id") != replay.get("run_id"):
        raise ValueError("missing or contradictory run identity")
    if any(replay.get(k) is not False for k in (
        "runtime_authenticated", "business_validated", "human_approval_authenticated",
        "live_remediation_authorized", "portal_integration_qualified"
    )):
        raise ValueError("untrusted replay asserts privileged state")
    safety = transport.get("safety")
    if not isinstance(safety, dict) or any(safety.get(k) is not v for k, v in (
        ("read_only", True), ("runtime_authenticated", False),
        ("remediation_authorized", False), ("portal_integration_qualified", False)
    )):
        raise ValueError("unsafe transport")
    if not isinstance(replay.get("run_id"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,95}", replay["run_id"]):
        raise ValueError("unsafe replay run_id")
    scene_plan(transport.get("scenario"), transport)  # Validates nine exact views.
    safe_frames = [{
        "step": frame["step"], "application": frame["application"],
        "expected_view": frame["expected_view"],
        "expected_state": cue.required_state,
        "capture_status": frame["capture_status"],
        "runtime_verified": False, "action_allowed": False,
    } for cue, frame in zip(CUES, transport["frames"])]
    digest = replay.get("input_content_sha256")
    if (not isinstance(digest, dict) or set(digest) != {"run", "ledger", "evidence"}
            or any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in digest.values())):
        raise ValueError("invalid replay input digest")
    if set(bindings) - set(_ALLOWED_SOURCES):
        raise ValueError("unknown STAR cue binding")
    frames = replay.get("frames")
    if not isinstance(frames, list) or len(frames) > 5000:
        raise ValueError("invalid replay frames")
    lookup = {}
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError("invalid replay frame")
        src, index = frame.get("source"), frame.get("source_index")
        if src not in {"events", "stages", "analyses", "critiques", "policy_decisions"} or type(index) is not int or index < 1:
            raise ValueError("invalid replay source reference")
        key = (src, index)
        if key in lookup:
            raise ValueError("duplicate replay source reference")
        lookup[key] = frame
    used = set()
    overlay = []
    previous_declared_time = None
    for cue in CUES:
        binding = bindings.get(cue.cue)
        if binding is None:
            overlay.append({"cue": cue.cue, "binding_status": "unbound", "replay_reference": None})
            continue
        if not isinstance(binding, dict) or set(binding) != _ALLOWED_BINDING_KEYS:
            raise ValueError("binding must contain only source and source_index")
        source, index = binding["source"], binding["source_index"]
        if source not in _ALLOWED_SOURCES[cue.cue] or type(index) is not int or index < 1:
            raise ValueError("incompatible scene-to-source binding")
        key = (source, index)
        if key not in lookup or key in used:
            raise ValueError("missing or reused replay frame")
        used.add(key)
        source_frame = lookup[key]
        timestamp = source_frame.get("timestamp")
        if timestamp is not None:
            if not isinstance(timestamp, str) or len(timestamp) > 40:
                raise ValueError("unsafe declared timestamp")
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("unsafe declared timestamp") from exc
            if dt.tzinfo is None or dt.utcoffset() is None:
                raise ValueError("unqualified declared timestamp")
            # Declared timestamps must be ordered; this does NOT attest runtime.
            if previous_declared_time is not None and dt < previous_declared_time:
                raise ValueError("nonmonotonic declared STAR checkpoint chronology")
            previous_declared_time = dt
        overlay.append({
            "cue": cue.cue,
            "binding_status": "operator_declared_unattested",
            "replay_reference": {
                "source": source, "source_index": index,
                "declared_timestamp": timestamp,
            },
        })
    return {
        "schema": "star-legacy-portal-binding/v1",
        "run_id": replay["run_id"],
        "scenario": transport["scenario"],
        "replay_status": replay["status"],
        "replay_input_content_sha256": replay.get("input_content_sha256"),
        "chronology_proven_from_declared_timestamps": replay.get("chronology_proven_from_declared_timestamps") is True,
        "storyboard": {
            "schema": "star-portal-transport-v1", "run_id": replay["run_id"],
            "scenario": transport["scenario"], "frames": safe_frames,
            "safety": {"read_only": True, "runtime_authenticated": False,
                       "portal_integration_qualified": False, "remediation_authorized": False},
        },
        "bindings": overlay,
        "safety": {
            "synthetic_only": True, "read_only": True,
            "runtime_authenticated": False, "business_validated": False,
            "human_approval_authenticated": False,
            "live_remediation_authorized": False,
            "portal_integration_qualified": False,
        },
    }


def export_legacy_portal_binding(manifest: Path, root: Path, scenario: str,
                                 run: Mapping, ledger: Mapping, evidence: Mapping,
                                 bindings: Mapping) -> dict:
    """Read a local capture manifest and build an offline portal-ready document."""
    transport = export_storyboard(manifest, root, scenario)
    replay = build_replay(run, ledger, evidence)
    return bind_replay_to_transport(transport, replay, bindings)
