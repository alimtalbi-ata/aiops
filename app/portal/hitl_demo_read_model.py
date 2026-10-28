"""Read-only Golden Demo HITL artifact view. Never an approval or execution API.

Artifacts are produced by demo.hitl_golden_demo in an isolated sandbox.
The portal never reads the HITL SQLite database or writes canonical Core state.
"""
import hashlib
import html
import json
import math
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
# Same read-only, no-store and restrictive browser posture as the synthetic
# ACME impact page from PR #36, without importing a module absent on this branch.
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    ),
}

router = APIRouter()
MAX_BYTES = 128 * 1024
STATES = ("AWAITING_HUMAN_APPROVAL", "APPROVED_FOR_DRY_RUN_ONLY", "DRY_RUN_PLANNED")
STEP_KEYS = frozenset({
    "schema", "proposal_id", "incident_id", "run_id", "recipe_id", "target_id",
    "params_hash", "binding_hash", "mode", "expires_at", "state", "receipt_id",
    "audit_actions", "source", "synthetic", "runtime_authenticated",
    "production_qualified", "execution_allowed", "effect_executed",
    "postchecks", "rollback",
})
TOP_KEYS = frozenset({
    "schema", "generated_at_utc", "provenance", "simulation_only",
    "runtime_authenticated", "production_qualified",
    "live_remediation_authorized", "effect_executed", "steps", "story_sha256",
})


def _read_file(path):
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ValueError("safe file opening unavailable")
    fd = os.open(path, os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0) |
                 getattr(os, "O_NONBLOCK", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError("invalid sandbox artifact file")
        with os.fdopen(fd, "rb", closefd=False) as f:
            raw = f.read(MAX_BYTES + 1)
        after = os.fstat(fd)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if fields(before) != fields(after) or len(raw) != after.st_size or len(raw) > MAX_BYTES:
            raise ValueError("unstable sandbox artifact")
        return raw
    finally:
        os.close(fd)


def validate_story(data):
    if not isinstance(data, dict) or set(data) != TOP_KEYS:
        raise ValueError("invalid HITL story envelope")
    if (data["schema"] != "aiops.hitl.sandbox-story.v1"
        or data["provenance"] != "LOCAL_SANDBOX_SQLITE_NOT_CORE"
        or any(data[k] is not False for k in (
            "runtime_authenticated", "production_qualified",
            "live_remediation_authorized", "effect_executed"))
        or data["simulation_only"] is not True):
        raise ValueError("HITL story is not explicitly sandbox-only")
    stamp = datetime.fromisoformat(data["generated_at_utc"])
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("UTC timestamp required")
    steps = data["steps"]
    if not isinstance(steps, list) or len(steps) != 3:
        raise ValueError("invalid HITL state sequence")
    binding_keys = ("proposal_id", "incident_id", "run_id", "recipe_id",
                    "target_id", "params_hash", "binding_hash", "mode")
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or set(step) != STEP_KEYS:
            raise ValueError("invalid HITL step schema")
        if (step["schema"] != "aiops.hitl.sandbox-status.v1"
            or step["state"] != STATES[i]
            or step["mode"] != "DEMO"
            or step["source"] != "LOCAL_SANDBOX_SQLITE_NOT_CORE"
            or step["synthetic"] is not True
            or any(step[k] is not False for k in (
                "runtime_authenticated", "production_qualified",
                "execution_allowed", "effect_executed"))
            or not isinstance(step["postchecks"], dict)
            or not step["postchecks"]
            or any(v != "NOT_EXECUTED" for v in step["postchecks"].values())
            or not isinstance(step["rollback"], dict)
            or step["rollback"].get("status") != "NOT_EXECUTED"
            or not isinstance(step["audit_actions"], list)):
            raise ValueError("unsafe or inconsistent HITL step")
        if any(not isinstance(step[k], str) or not step[k] for k in binding_keys):
            raise ValueError("missing HITL binding")
        if i and any(step[k] != steps[0][k] for k in binding_keys):
            raise ValueError("HITL binding changed during story")
        # The three views represent one proposal at one synthetic instant.
        # A rehashed artifact must not invent an expired or extended approval.
        expires = step["expires_at"]
        if (type(expires) not in (int, float) or not math.isfinite(expires)
            or not 0 < expires - stamp.timestamp() <= 3600
            or (i > 0 and expires != steps[0]["expires_at"])):
            raise ValueError("invalid HITL story expiration")
        proposal_id = step["proposal_id"]
        if (len(proposal_id) != 32
            or any(ch not in "0123456789abcdef" for ch in proposal_id)):
            raise ValueError("invalid HITL proposal identifier")
        # Recompute the canonical proposal binding instead of trusting a
        # self-consistent but forged story_sha256 and binding_hash.
        binding = {k: step[k] for k in (
            "incident_id", "run_id", "recipe_id", "target_id", "params_hash", "mode"
        )}
        params_digest = step["params_hash"]
        if (len(params_digest) != 64 or any(ch not in "0123456789abcdef" for ch in params_digest)):
            raise ValueError("invalid HITL parameter digest")
        canonical_binding = json.dumps(
            binding, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        expected_binding = hashlib.sha256(canonical_binding).hexdigest()
        if step["binding_hash"] != expected_binding:
            raise ValueError("HITL binding digest mismatch")
        if step["receipt_id"] is not None and i < 2:
            raise ValueError("premature receipt")
        if i == 2 and (not isinstance(step["receipt_id"], str)
                       or len(step["receipt_id"]) != 32
                       or any(ch not in "0123456789abcdef" for ch in step["receipt_id"])):
            raise ValueError("invalid dry-run receipt identifier")
        if step["audit_actions"] != [
            "PROPOSED",
            *(["APPROVED_SANDBOX_ONLY"] if i >= 1 else []),
            *(["DRY_RUN_PLAN_ISSUED"] if i == 2 else []),
        ]:
            raise ValueError("HITL audit does not match story state")
    digest = data["story_sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("missing story digest")
    canonical = json.dumps({k: v for k, v in data.items() if k != "story_sha256"},
                           sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if hashlib.sha256(canonical).hexdigest() != digest:
        raise ValueError("sandbox artifact digest mismatch")
    return data


def load_story():
    configured = os.getenv("AIOPS_HITL_DEMO_ARTIFACT", "")
    if not configured:
        return {"state": "NOT_CONFIGURED", "provenance": "NO_SANDBOX_ARTIFACT_CONFIGURED",
                "steps": [], "runtime_authenticated": False,
                "live_remediation_authorized": False}
    try:
        return validate_story(json.loads(_read_file(Path(configured))))
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError) as exc:
        raise HTTPException(503, "sandbox HITL artifact unavailable or invalid") from exc


@router.get("/api/demo/hitl", name="hitl_sandbox_story_json")
def hitl_story_json():
    return JSONResponse(load_story(), headers=HEADERS)


@router.get("/demo/hitl", response_class=HTMLResponse, name="hitl_sandbox_story_page")
def hitl_story_page():
    model = load_story()
    if not model.get("steps"):
        rows = "<p>NOT_CONFIGURED — aucune preuve de laboratoire fournie.</p>"
    else:
        rows = "".join(
            "<li><strong>" + html.escape(s["state"], quote=True) + "</strong>"
            " — incident " + html.escape(s["incident_id"], quote=True)
            + " / run " + html.escape(s["run_id"], quote=True)
            + " — reçu : " + html.escape(s["receipt_id"] or "ABSENT", quote=True)
            + " — postchecks et rollback : NOT_EXECUTED</li>"
            for s in model["steps"]
        )
        rows = "<ol>" + rows + "</ol>"
    page = ("<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            "<title>ACME HITL Lab — simulation uniquement</title></head><body>"
            "<main><h1>HITL Lab — Golden Demo</h1>"
            "<p>SIMULATION UNIQUEMENT. Source : SQLite sandbox locale, "
            "ni Core ni Temporal ni GLPI. Aucune approbation LIVE, aucune remédiation "
            "réelle, aucun postcheck exécuté, aucune preuve runtime authentifiée.</p>"
            + rows + "<p><a href='/'>Retour au portail</a></p></main></body></html>")
    return HTMLResponse(page, headers=HEADERS)
