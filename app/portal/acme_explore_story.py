"""Explore/Story: authenticated, stateless navigation of one local synthetic ACME fixture.

No runtime command, Core/GLPI/n8n request, tenant inventory or LIVE action.
The viewer token gates every control request; cursor state belongs only to the browser.
"""
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from portal.acme_impact_read_model import _load_or_503
from portal.noc_runtime import _require_portal_read_auth, _noc_json_response

router = APIRouter()
ACTIONS = frozenset({"start", "pause", "advance", "reset", "replay"})
MODES = frozenset({"explore", "story"})
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACME — Explore / Story (simulation)</title>
<style>
body{margin:0;background:#081522;color:#ecf4ff;font:15px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:24px}
a{color:#90d5ff}header{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.panel{background:#10243a;border:1px solid #2a4b65;border-radius:14px;padding:18px;margin:14px 0}
button{background:#2878b7;color:white;border:0;border-radius:8px;padding:10px 14px;margin:4px;cursor:pointer}
button:focus-visible,input:focus-visible{outline:3px solid #ffda7a}
button[aria-pressed=true]{background:#16634d}
input{background:#06111e;color:white;border:1px solid #63839a;padding:10px;border-radius:8px}
.muted{color:#adc1d1}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
ol{padding-left:28px}li{padding:6px}li.current{color:#ffda7a;font-weight:bold}
strong{overflow-wrap:anywhere}#step-detail{white-space:pre-wrap}
</style></head><body><main>
<header><a href="/">← Portail unique</a><a href="/demo/acme-impact">Graphe ACME (simulation)</a></header>
<h1>ACME · Explore / Story</h1>
<p>SIMULATED_TARGET — même fixture SAN P1 → Payments P2 dans les deux modes.
Aucune preuve LIVE, capture, écriture GLPI, commande Core ou remédiation.</p>
<section class="panel" aria-label="Modes">
<button type="button" id="mode-explore" aria-pressed="true">Explore · pas à pas</button>
<button type="button" id="mode-story" aria-pressed="false">Story · lecture guidée</button>
<p id="mode-description" class="muted">Explore : avancez manuellement dans les checkpoints fictifs.</p>
</section>
<section class="panel" aria-label="Commandes authentifiées">
<label for="story-token">Jeton viewer (mémoire uniquement)</label>
<input type="password" id="story-token" autocomplete="off" aria-label="Jeton viewer">
<button type="button" id="start">Start</button><button type="button" id="pause">Pause</button>
<button type="button" id="advance">Advance</button><button type="button" id="reset">Reset</button>
<button type="button" id="replay">Replay</button><button type="button" id="clear">Effacer la session</button>
<p id="story-status" role="status">UNKNOWN — jeton viewer requis</p>
</section>
<section class="grid">
<div class="panel"><h2>Scénario</h2><p id="scenario">UNKNOWN — aucune lecture authentifiée</p>
<p id="source" class="muted">Provenance : UNKNOWN</p></div>
<div class="panel"><h2>Checkpoint courant</h2><p id="step-title">UNKNOWN</p>
<p id="step-detail" class="muted">Aucune preuve runtime attestée</p></div>
</section>
<section class="panel"><h2>Timeline · checkpoints de scénario, pas événements runtime</h2>
<ol id="timeline"><li>UNKNOWN — authentification requise</li></ol></section>
</main><script src="/assets/acme-explore-story.js" defer></script></body></html>"""


@router.get("/demo/explore-story", response_class=HTMLResponse)
def explore_story_page():
    """Public shell only: no fixture data or token embedded in HTML."""
    return HTMLResponse(PAGE, headers=HEADERS)


@router.get("/assets/acme-explore-story.js")
def explore_story_script():
    return FileResponse(Path(__file__).with_name("acme_explore_story_client.js"),
                        media_type="application/javascript", headers=HEADERS)


@router.post("/api/demo/explore-story/control")
def explore_story_control(payload: dict, authorization: str | None = Header(default=None)):
    """Pure step selection. Authenticate before opening/validating local fixture."""
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return _noc_json_response({"detail": exc.detail}, status_code=exc.status_code)

    if (type(payload) is not dict or set(payload) != {"action", "cursor", "mode"}
            or type(payload["action"]) is not str or payload["action"] not in ACTIONS
            or type(payload["mode"]) is not str or payload["mode"] not in MODES
            or type(payload["cursor"]) is not int or payload["cursor"] < 0):
        return _noc_json_response({"detail": "invalid_story_control"}, status_code=422)

    try:
        model = _load_or_503()
    except HTTPException:
        return _noc_json_response({"state": "UNKNOWN", "detail": "synthetic_fixture_unavailable"},
                                  status_code=503)

    steps = model["checkpoint_evidence"]
    if not steps or payload["cursor"] >= len(steps):
        return _noc_json_response({"detail": "invalid_story_cursor"}, status_code=422)

    action, mode, cursor = payload["action"], payload["mode"], payload["cursor"]
    if action in {"reset", "replay"} or (action == "start" and cursor == len(steps) - 1):
        cursor = 0
    elif action == "advance":
        cursor = min(cursor + 1, len(steps) - 1)
    playing = mode == "story" and action in {"start", "advance", "replay"} and cursor < len(steps) - 1
    # Strict projection: no raw fixture, secret, backend URLs or unqualified evidence.
    timeline = [{"cue": s["cue"], "service": s["service"], "view": s["view"],
                 "status": "MISSING"} for s in steps]
    return _noc_json_response({
        "schema": "aiops.acme-explore-story.v1",
        "mode": mode, "action": action, "cursor": cursor, "playing": playing,
        "provenance": "SIMULATED_TARGET", "source_sha256": model["source_sha256"],
        "scenario": {
            "run_id": model["run_id"],
            "incident_id": model["incident_id"],
            "impact_incident_id": model["impact_incident_id"],
            "impact_path": model["impact_path"],
            "ticket_id": None, "event_timestamp_utc": None,
        },
        "timeline": timeline, "step": timeline[cursor],
        "runtime_attested": False, "production_qualified": False,
        "live_remediation_authorized": False,
    })
