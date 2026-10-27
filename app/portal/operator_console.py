"""Read-only operator console shell; the API enforces RBAC, not this page.

The browser never persists bearer credentials and never treats API reads as
authenticated runtime evidence. No write routes are exposed here.
"""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()
HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"
    ),
}
HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACME AioOps — Vue opérateur</title>
<style>
body{font:15px system-ui,sans-serif;background:#07111d;color:#e9f2f8;max-width:1100px;margin:auto;padding:24px}
a{color:#8fd0ff}section{border:1px solid #315068;background:#0d2031;border-radius:12px;padding:16px;margin:18px 0}
label{display:block;margin:12px 0}input{background:#101e30;color:#fff;border:1px solid #69859b;padding:9px;width:min(90%,460px)}
button{background:#2188c7;color:white;border:0;border-radius:8px;padding:10px 14px;margin-right:8px}
button:focus-visible,input:focus-visible{outline:3px solid #f3cd6b}
.muted{color:#b4c5d4}li{padding:6px 0;overflow-wrap:anywhere}
</style>
<script src="/operator/console.js" defer></script></head>
<body><nav><a href="/">Portail</a> / Vue opérateur</nav>
<h1>Incident / Run / Evidence</h1>
<p class="muted">Lecture seule — API interne non attestée. Aucune remédiation LIVE.
Aucun jeton stocké dans le navigateur. États non prouvés : UNKNOWN.</p>
<section><h2>Accès opérateur</h2>
<form id="access" autocomplete="off">
<label for="token">Jeton de lecture (viewer / operator)</label>
<input id="token" type="password" autocomplete="new-password" required aria-label="Jeton de lecture">
<button type="submit">Lire les ressources</button>
<button id="clear" type="button">Effacer la session</button>
</form>
<p id="auth-state" role="status" aria-live="polite">UNKNOWN — authentification non effectuée</p>
<p id="role-state" class="muted">Rôle : UNKNOWN</p></section>
<section><h2>Incidents</h2><p id="incidents-state" role="status">UNKNOWN</p><ul id="incidents-items"></ul></section>
<section><h2>Runs</h2><p id="runs-state" role="status">UNKNOWN</p><ul id="runs-items"></ul></section>
<section><h2>Evidence — métadonnées uniquement</h2>
<p id="evidence-state" role="status">UNKNOWN</p><ul id="evidence-items"></ul></section>
</body></html>"""


@router.get("/operator", response_class=HTMLResponse)
def operator_console():
    return HTMLResponse(HTML, headers=HEADERS)


@router.get("/operator/console.js")
def operator_console_script():
    return FileResponse(
        Path(__file__).with_name("operator_console.js"),
        media_type="text/javascript; charset=utf-8",
        headers=HEADERS,
    )
