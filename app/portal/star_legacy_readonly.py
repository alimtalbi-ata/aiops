"""Opt-in, synthetic-only STAR replay route for the EXISTING portal; no runtime I/O."""
from __future__ import annotations
import base64
import binascii
from datetime import datetime
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import re
import stat
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

router = APIRouter()
RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,95}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
CUES = (
    ("detect", "grafana", "alert_dashboard", "firing"),
    ("correlate", "n8n", "ingress_execution", "completed"),
    ("enrich", "n8n", "context_execution", "completed"),
    ("analyze", "n8n", "analyst_critic_execution", "completed"),
    ("ticket", "glpi", "incident_ticket", "open"),
    ("approve", "glpi", "hitl_decision", "approved_simulation_only"),
    ("simulate", "n8n", "simulation_execution", "completed"),
    ("verify", "grafana", "recovery_dashboard", "recovered"),
    ("close", "glpi", "incident_followups", "closed"),
)
SOURCES = {"detect": {"events"}, "correlate": {"events", "stages"},
           "enrich": {"stages"}, "analyze": {"analyses", "critiques"},
           "ticket": {"stages"}, "approve": {"policy_decisions"},
           "simulate": {"stages", "policy_decisions"},
           "verify": {"stages"}, "close": {"stages"}}
SAFETY = {"read_only": True, "synthetic_only": True,
          "runtime_authenticated": False, "business_validated": False,
          "human_approval_authenticated": False, "live_remediation_authorized": False,
          "portal_integration_qualified": False}
BOARD_SAFETY = {"read_only": True, "runtime_authenticated": False,
                "portal_integration_qualified": False, "remediation_authorized": False}
HEADERS = {"Cache-Control": "no-store, max-age=0", "X-Content-Type-Options": "nosniff",
           "Referrer-Policy": "no-referrer",
           "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"}


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _no_constant(_):
    raise ValueError("non-finite JSON number")


def _read(root: Path, run_id: str) -> dict:
    if not RUN.fullmatch(run_id) or root.is_symlink():
        raise ValueError("invalid artifact location")
    # Directory descriptor prevents symlink swaps of the leaf files.
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        def one(suffix, limit):
            fd = os.open(run_id + suffix, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                meta = os.fstat(fd)
                if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
                    raise ValueError("unsafe artifact")
                raw = os.read(fd, limit + 1)
                if len(raw) > limit:
                    raise ValueError("oversize artifact")
                return raw
            finally:
                os.close(fd)
        raw = one(".json", 262144)
        digest = one(".sha256", 128).decode("ascii").strip()
    finally:
        os.close(directory)
    if not SHA.fullmatch(digest) or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), digest):
        raise ValueError("artifact digest mismatch")
    doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_no_constant)
    if not isinstance(doc, dict):
        raise ValueError("artifact must be object")
    return doc


def validate(doc: dict, run_id: str) -> tuple[str, list[dict]]:
    if not isinstance(doc, dict) or set(doc) != {
        "schema", "run_id", "scenario", "replay_status", "replay_input_content_sha256",
        "chronology_proven_from_declared_timestamps", "storyboard", "bindings", "safety"}:
        raise ValueError("invalid binding fields")
    if doc["schema"] != "star-legacy-portal-binding/v1" or doc["run_id"] != run_id or not RUN.fullmatch(run_id):
        raise ValueError("invalid identity/schema")
    if type(doc["chronology_proven_from_declared_timestamps"]) is not bool:
        raise ValueError("invalid chronology claim")
    if doc["scenario"] not in ("SAN_FABRIC_P1", "PAYMENTS_P2") or doc["replay_status"] not in ("BLOCKED", "RESOLVED"):
        raise ValueError("invalid replay scenario/status")
    if doc["safety"] != SAFETY or type(doc["safety"]) is not dict:
        raise ValueError("unsafe replay assertion")
    hashes = doc["replay_input_content_sha256"]
    if not isinstance(hashes, dict) or set(hashes) != {"run", "ledger", "evidence"} or any(
        not isinstance(value, str) or not SHA.fullmatch(value) for value in hashes.values()):
        raise ValueError("invalid replay input digests")
    board = doc["storyboard"]
    if not isinstance(board, dict) or set(board) != {"schema", "run_id", "scenario", "frames", "safety"}:
        raise ValueError("invalid storyboard")
    if board["schema"] != "star-portal-transport-v1" or board["run_id"] != run_id or board["scenario"] != doc["scenario"]:
        raise ValueError("contradictory storyboard")
    if type(board["safety"]) is not dict or board["safety"] != BOARD_SAFETY:
        raise ValueError("unsafe storyboard")
    frames, bindings = board["frames"], doc["bindings"]
    if not isinstance(frames, list) or not isinstance(bindings, list) or len(frames) != 9 or len(bindings) != 9:
        raise ValueError("incomplete checkpoints")
    used, previous, scenes = set(), None, []
    for (cue, service, view, expected), frame, binding in zip(CUES, frames, bindings):
        if not isinstance(frame, dict) or set(frame) != {
            "step", "application", "expected_view", "expected_state", "capture_status", "runtime_verified", "action_allowed"}:
            raise ValueError("invalid checkpoint")
        if (frame["step"], frame["application"], frame["expected_view"], frame["expected_state"]) != (cue, service, view, expected):
            raise ValueError("wrong checkpoint view")
        if frame["runtime_verified"] is not False or frame["action_allowed"] is not False or frame["capture_status"] not in (
            "missing", "simulated", "integrity_checked"):
            raise ValueError("untrusted capture claim")
        if not isinstance(binding, dict) or set(binding) != {"cue", "binding_status", "replay_reference"} or binding["cue"] != cue:
            raise ValueError("invalid binding")
        status, ref = binding["binding_status"], binding["replay_reference"]
        label = "aucune référence"
        if status == "unbound" and ref is None:
            pass
        elif status == "operator_declared_unattested" and isinstance(ref, dict) and set(ref) == {
            "source", "source_index", "declared_timestamp"}:
            source, index, timestamp = ref["source"], ref["source_index"], ref["declared_timestamp"]
            if source not in SOURCES[cue] or type(index) is not int or index < 1 or (source, index) in used:
                raise ValueError("invalid/duplicate replay reference")
            used.add((source, index))
            if timestamp is not None:
                if not isinstance(timestamp, str) or len(timestamp) > 40:
                    raise ValueError("invalid timestamp")
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if dt.tzinfo is None or dt.utcoffset() is None or (previous is not None and dt < previous):
                    raise ValueError("unqualified/nonmonotonic timestamp")
                previous = dt
            label = f"{source} #{index} — déclaration opérateur non attestée"
        else:
            raise ValueError("invalid binding state")
        scenes.append({"cue": cue, "app": service, "view": view,
                       "capture": frame["capture_status"], "reference": label})
    return doc["scenario"], scenes


def render(doc: dict, run_id: str) -> str:
    scenario, scenes = validate(doc, run_id)
    cards = "".join(
        f'<section id="scene-{i}"><h2>{i}. {html.escape(row["cue"])}</h2>'
        f'<p>{html.escape(row["app"].upper())} · {html.escape(row["view"])}</p>'
        f'<p>Capture déclarée (non attestée) : {html.escape(row["capture"])}</p>'
        f'<p>{html.escape(row["reference"])}</p></section>'
        for i, row in enumerate(scenes, 1))
    nav = " ".join(f'<a href="#scene-{i}">Étape {i}</a>' for i in range(1, 10))
    return ("<!doctype html><html lang='fr'><meta charset='utf-8'><title>STAR — Replay synthétique</title>"
            "<style>body{font:16px system-ui;background:#101e30;color:#fff;max-width:960px;margin:2rem auto}"
            "section{padding:1rem;margin:1rem 0;border:1px solid #456;background:#20354c}a{color:#9df}</style>"
            f"<h1>ACME STAR — {html.escape(scenario)}</h1><p>Run : {html.escape(run_id)}</p>"
            "<p><strong>SYNTHÉTIQUE : origine non authentifiée, approbation HITL et clôture métier non attestées. "
            "Aucune remédiation LIVE. SHA256 = intégrité locale uniquement.</strong></p>"
            f"<nav>{nav}</nav>{cards}</html>")


@router.get("/demo/star-replay/{run_id}", response_class=HTMLResponse)
def offline_replay_page(run_id: str, request: Request, authorization: str | None = Header(default=None)):
    if os.getenv("AIOPS_STAR_REPLAY_VIEW_ENABLED") != "true":
        raise HTTPException(404, "STAR replay disabled")
    if not RUN.fullmatch(run_id):
        raise HTTPException(404, "invalid run")
    # Never accept Basic credentials on plaintext remote HTTP. Forwarded headers are not trusted.
    peer = request.client.host if request.client else ""
    if request.url.scheme != "https" and peer not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "secure transport required")
    user, password = os.getenv("AIOPS_STAR_VIEW_USER"), os.getenv("AIOPS_STAR_VIEW_PASSWORD")
    if not user or not password:
        raise HTTPException(503, "operator authentication not configured")
    try:
        scheme, token = (authorization or "").split(" ", 1)
        if scheme.lower() != "basic" or len(token) > 1024:
            raise ValueError("bad scheme")
        identity, supplied = base64.b64decode(token, validate=True).decode("utf-8").split(":", 1)
        ok = hmac.compare_digest(identity, user) & hmac.compare_digest(supplied, password)
    except (ValueError, UnicodeError, binascii.Error):
        ok = False
    if not ok:
        raise HTTPException(401, "authentication required", headers={"WWW-Authenticate": 'Basic realm="AIOps STAR offline"'})
    root = os.getenv("AIOPS_STAR_OFFLINE_DIR")
    if not root:
        raise HTTPException(503, "offline artifact directory not configured")
    try:
        page = render(_read(Path(root), run_id), run_id)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError):
        raise HTTPException(503, "offline STAR artifact not qualified") from None
    return HTMLResponse(page, headers=HEADERS)
