"""Read-only GLPI handoff inside the existing Portal, never a second ITSM.

No GLPI or Core request is permitted until an independently verified,
server-derived actor+tenant ACL and authoritative ticket/Run mapping exist.
The current shared viewer token authenticates the Portal request only.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from portal.noc_runtime import _require_portal_read_auth

router = APIRouter()
SECURITY = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}

# No ticket, CI, user, entity, permission or business-impact data is embedded.
# These labels describe intended GLPI-native views, not an installed integration.
PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GLPI / ITSM — Portal read-only handoff</title>
<style>
body{margin:0;background:#07111d;color:#e9f2f8;font:15px/1.55 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:24px}
a{color:#91d6ff}a:focus-visible,select:focus-visible{outline:3px solid #ffda7a;outline-offset:3px}
nav{display:flex;gap:18px;flex-wrap:wrap}
.panel{background:#0c1d2d;border:1px solid #31506a;border-radius:12px;padding:18px;margin:16px 0}
.muted{color:#b5c9d7}.status{font-weight:700;color:#ffda7a}
dl{display:grid;grid-template-columns:minmax(180px,1fr) 2fr;gap:8px}
dt{font-weight:700}dd{margin:0;color:#b5c9d7}
@media(max-width:600px){dl{grid-template-columns:1fr}}
</style></head><body><main>
<nav aria-label="Navigation Portal"><a href="/">Cockpit AIOps</a>
<a href="/#integrations">Liens natifs configurés, dont GLPI</a>
<a href="/demo/explore-story">Demo Studio / Story</a></nav>
<h1>GLPI / ITSM — point de passage opérateur</h1>
<p role="note" data-story-provenance="SYNTHETIC">ACME P1 SAN→Payments —
<strong>SYNTHETIC</strong> uniquement. Aucun ticket, CI, impact ou Run réel attesté.</p>
<p role="status" class="status">UNKNOWN — ACL acteur+tenant non qualifiée.
Aucune lecture GLPI/Core, aucun état CONNECTED.</p>
<p>GLPI reste le système de référence pour tickets, CMDB, profils et actions.
Ce Portal ne remplace ni les pages natives ni leurs contrôles de permission.</p>
<section class="panel" aria-labelledby="ticket"><h2 id="ticket">Fiche ticket enrichie — non chargée</h2>
<dl>
<dt>Ticket / entité / catégorie / formulaire / template</dt><dd>UNKNOWN — lecture GLPI native non attestée</dd>
<dt>CI / service métier / dépendances Twin</dt><dd>UNKNOWN — association tenant-scoped absente</dd>
<dt>Événements NOC corrélés / Incident / Run AIOps</dt><dd>UNKNOWN — lien canonique non vérifié</dd>
<dt>Evidence sourcées / diagnostic Analyst et Critic</dt><dd>UNKNOWN — provenance et fraîcheur absentes</dd>
<dt>Proposition / Policy / HITL / Verification</dt><dd>UNKNOWN — aucune approbation navigateur</dd>
<dt>SLA / OLA / maintenance / historique / audit</dt><dd>UNKNOWN — lecture autorisée non installée</dd>
</dl></section>
<section class="panel" aria-labelledby="views"><h2 id="views">Vues NOC / ITSM par rôle</h2>
<p class="muted">Matrice de besoins, pas une décision RBAC ni des droits GLPI observés.</p>
<dl>
<dt>N1</dt><dd>Tri, priorité, acquittement, consignes et escalade — permissions UNKNOWN</dd>
<dt>N2</dt><dd>Corrélation, diagnostic et coordination incident — permissions UNKNOWN</dd>
<dt>N3</dt><dd>Analyse problème, changement proposé et vérification — permissions UNKNOWN</dd>
<dt>Manager</dt><dd>SLA/OLA, incidents majeurs, audit et reporting — permissions UNKNOWN</dd>
</dl>
<label for="priority">Filtre priorité P1–P4 (désactivé sans données autorisées)</label>
<select id="priority" disabled aria-disabled="true">
<option>P1–P4 — UNKNOWN</option><option>P1</option><option>P2</option>
<option>P3</option><option>P4</option></select>
<p class="muted">Aucune action commentaire, assignation ou approbation en DEMO.
Les profils, entités, catégories, règles métier, plugins, formulaires,
templates et pages natives GLPI n'ont pas été inspectés sur une instance autorisée.</p>
</section>
<section class="panel" aria-labelledby="source"><h2 id="source">Source et fraîcheur</h2>
<p>Source API : UNKNOWN / non autorisée. Observé à : UNKNOWN.
Fraîcheur : UNKNOWN. Contrat Core ticket↔Run : non intégré dans ce Portal.</p>
<p>Le lien GLPI natif éventuel se consulte dans les intégrations configurées
après authentification; sa présence ne prouve pas la disponibilité du service.</p>
</section></main></body></html>"""


@router.get("/itsm", response_class=HTMLResponse, name="portal_glpi_operator_handoff")
def glpi_operator_page():
    """Anonymous safe shell: zero tenant content and zero upstream requests."""
    return HTMLResponse(PAGE, headers=SECURITY)


@router.get("/api/portal/itsm", name="portal_glpi_readonly_status")
def glpi_readonly_status(authorization: str | None = Header(default=None)):
    """Authenticate before any read; the shared bearer never grants tenant ACL."""
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        status = exc.status_code
        return JSONResponse(
            {"state": "UNAUTHORIZED" if status in (401, 403) else "UNKNOWN",
             "reason": str(exc.detail)},
            status_code=status,
            headers={**SECURITY, **({"WWW-Authenticate": "Bearer"} if status == 401 else {})},
        )
    # No Core/GLPI API is called. Even a valid token or forged role/tenant
    # header cannot reveal whether a ticket, entity or Run exists.
    return JSONResponse({
        "schema": "aiops.portal.glpi-handoff.v1",
        "state": "UNKNOWN",
        "reason": "TENANT_ACL_NOT_QUALIFIED",
        "connection_state": "UNKNOWN",
        "source": "NO_AUTHORIZED_GLPI_TICKET_RUN_READ",
        "source_freshness": "UNKNOWN",
        "tenant_acl_qualified": False,
        "runtime_attested": False,
        "glpi_write_enabled": False,
        "live_remediation_authorized": False,
    }, status_code=503, headers=SECURITY)
