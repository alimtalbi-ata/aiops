"""Read-only GLPI handoff inside the existing Portal, never a second ITSM.

No GLPI or Core request is permitted until an independently verified,
server-derived actor+tenant ACL and authoritative ticket/Run mapping exist.
The current shared viewer token authenticates the Portal request only.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from portal.acme_run_detail import _oidc_cookie_supplied
from portal.core_acl_consumer import consume_run_acl
from portal.noc_runtime import _require_portal_read_auth

router = APIRouter()
SECURITY = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; "
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
a{color:#91d6ff}a:focus-visible,select:focus-visible,button:focus-visible{outline:3px solid #ffda7a;outline-offset:3px}
button{background:#204b69;color:#fff;border:1px solid #8eb9d4;border-radius:8px;padding:9px 12px;cursor:pointer}button:disabled{opacity:.65;cursor:not-allowed}
nav{display:flex;gap:18px;flex-wrap:wrap}
.panel{background:#0c1d2d;border:1px solid #31506a;border-radius:12px;padding:18px;margin:16px 0}
.muted{color:#b5c9d7}.status{font-weight:700;color:#ffda7a}
.journey{display:flex;flex-wrap:wrap;gap:10px;list-style:decimal;padding-left:24px}
.journey li{padding:4px 10px 4px 0}.journey [aria-current=page]{font-weight:700}
dl{display:grid;grid-template-columns:minmax(180px,1fr) 2fr;gap:8px}
table{width:100%;border-collapse:collapse}th,td{border:1px solid #31506a;padding:10px;text-align:left}caption{text-align:left;color:#b5c9d7}
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
Aucune lecture GLPI/Core. Connecteur ticket↔Run : NOT_INSTALLED ; jamais CONNECTED.</p>
<section class="panel" aria-labelledby="human-rights-title">
<h2 id="human-rights-title">Contrôle d'accès humain GLPI — lecture seule</h2>
<p>Une identité IdP ne vaut pas un droit GLPI. READ exige un profil et une entité
natifs actifs ; READMY exige en plus la preuve native de propriété ou visibilité
du ticket. Le lien Core Incident/Run/ticket, le signataire et la révocation
doivent être attestés indépendamment.</p>
<button type="button" id="glpi-check" aria-controls="glpi-check-status">Vérifier mon état d'accès</button>
<p id="glpi-check-status" role="status" aria-live="polite">UNKNOWN — contrôle non demandé.</p>
<div id="glpi-source-readiness" role="group" aria-label="Origine et fraîcheur des autorisations">
<p id="glpi-source-provenance" role="note">Provenance : PORTAL_CONTRACT_ONLY ; observé à : UNKNOWN ;
fraîcheur : UNKNOWN. Le producteur Core PG16 est un contrat source, pas un droit humain GLPI.</p>
<table aria-describedby="glpi-source-provenance"><caption>Préconditions indépendantes — aucune lecture métier</caption>
<thead><tr><th scope="col">Autorité requise</th><th scope="col">État</th></tr></thead>
<tbody>
<tr><th scope="row">IdP subject → GLPI User, mapping gouverné</th><td data-authority-check="idp">UNKNOWN — non attesté</td></tr>
<tr><th scope="row">GLPI Profile / Entity / Ticket READ ou READMY + propriété</th><td data-authority-check="glpi">UNKNOWN — non attesté</td></tr>
<tr><th scope="row">Core PG16 Run → Incident → ticket, signataire distinct de l'IdP</th><td data-authority-check="core">UNKNOWN — non attesté</td></tr>
<tr><th scope="row">Nonce/JTI atomique, révocation et fraîcheur</th><td data-authority-check="replay">UNKNOWN — non attesté</td></tr>
</tbody></table></div>
<dl><dt>IdP → User GLPI</dt><dd>UNKNOWN — mapping non attesté</dd>
<dt>Profile / Entity / Ticket READ</dt><dd>UNKNOWN — droits natifs non attestés</dd>
<dt>READMY / propriété du ticket</dt><dd>UNKNOWN — propriété non attestée</dd>
<dt>Core Run / ticket / signer / nonce</dt><dd>UNKNOWN — liaison et révocation non attestées</dd></dl>
<p><button type="button" disabled aria-disabled="true">Commenter</button>
<button type="button" disabled aria-disabled="true">Assigner</button>
<button type="button" disabled aria-disabled="true">Approuver HITL</button></p>
<p class="muted">Actions désactivées ; aucun accès métier, approbation ou dispatch
ne peut être déduit du résultat de ce contrôle.</p>
</section>
<p>GLPI reste le système de référence pour tickets, CMDB, profils et actions.
Ce Portal ne remplace ni les pages natives ni leurs contrôles de permission.</p>
<nav class="panel" aria-labelledby="journey-title">
<h2 id="journey-title">Parcours opérateur unique — lecture seule</h2>
<p class="muted">Étapes de navigation, pas des données attestées. Source et fraîcheur :
UNKNOWN. Aucun deep link vers un ticket ou Run non autorisé.</p>
<ol class="journey" data-journey-provenance="SYNTHETIC">
<li>Incident — UNKNOWN</li><li>Run — UNKNOWN</li>
<li>Evidence — UNKNOWN</li><li>AI Ledger — UNKNOWN</li>
<li>Policy — UNKNOWN</li><li>HITL — UNKNOWN</li>
<li>Verification — UNKNOWN</li>
<li><a href="/itsm" aria-current="page">GLPI</a> — NOT_INSTALLED</li>
</ol></nav>
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
<section class="panel" aria-labelledby="queue"><h2 id="queue">File opérateur P1–P4 / SLA — non chargée</h2>
<p id="queue-unavailable" role="note">NOT_INSTALLED — aucune API GLPI authentifiée et
tenant-scoped ne fournit la file, les délais SLA/OLA ou les fenêtres de maintenance.
Aucun ticket ni compteur n'est déduit des fixtures SYNTHETIC.</p>
<table aria-describedby="queue-unavailable">
<caption>État de la file ITSM, sans enregistrement client</caption>
<thead><tr><th scope="col">Priorité</th><th scope="col">Ticket</th>
<th scope="col">SLA / OLA</th><th scope="col">Source / fraîcheur</th></tr></thead>
<tbody><tr><td colspan="4">UNKNOWN — aucune ligne affichable avant ACL acteur,
tenant et entité GLPI vérifiée côté serveur.</td></tr></tbody>
</table>
<p>Calendrier de maintenance : UNKNOWN. Historique et journal d'audit : UNKNOWN.
Les permissions N1/N2/N3/manager restent celles de GLPI, non inférées ici.</p>
</section>
<section class="panel" aria-labelledby="source"><h2 id="source">Source et fraîcheur</h2>
<p>Source API : UNKNOWN / non autorisée. Observé à : UNKNOWN.
Fraîcheur : UNKNOWN. Contrat Core ticket↔Run : NOT_INSTALLED dans ce Portal.</p>
<p>Le lien GLPI natif éventuel se consulte dans les intégrations configurées
après authentification; sa présence ne prouve pas la disponibilité du service.</p>
</section></main><script src="/assets/portal-glpi-authority.js" defer></script></body></html>"""


@router.get("/itsm", response_class=HTMLResponse, name="portal_glpi_operator_handoff")
def glpi_operator_page():
    """Anonymous safe shell: zero tenant content and zero upstream requests."""
    return HTMLResponse(PAGE, headers=SECURITY)


@router.get("/assets/portal-glpi-authority.js")
def glpi_authority_script():
    """Static same-origin status client; never contains identity or bearer."""
    return FileResponse(Path(__file__).with_name("glpi_authority_client.js"),
                        media_type="application/javascript", headers=SECURITY)


@router.get("/api/portal/itsm", name="portal_glpi_readonly_status")
def glpi_readonly_status(request: Request,
                         authorization: str | None = Header(default=None)):
    """OIDC cookie is explicit identity; never downgrade it to viewer bearer.

    A valid OIDC session still cannot grant native GLPI READ or READMY.
    This endpoint performs no Core/GLPI request or ticket lookup.
    """
    if _oidc_cookie_supplied(request):
        status, reason = consume_run_acl(request, "RUN-UNQUALIFIED")
        if status != 503:
            return JSONResponse(
                {"state": "UNAUTHORIZED", "reason": reason},
                status_code=401,
                headers={**SECURITY, "WWW-Authenticate": "Bearer"},
            )
    else:
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
    # Constant projection independent of actor, tenant, Run or ticket existence.
    # No source is queried: even READ-shaped mock responses are not authority.
    return JSONResponse({
        "schema": "aiops.portal.glpi-handoff.v1",
        "state": "UNKNOWN",
        "reason": "TENANT_ACL_NOT_QUALIFIED",
        "connection_state": "NOT_INSTALLED",
        "source": "NO_AUTHORIZED_GLPI_TICKET_RUN_READ",
        "source_freshness": "UNKNOWN",
        "human_authority": {
            "idp_subject_glpi_user": "UNKNOWN",
            "native_user_profile_entity_ticket_read": "UNKNOWN",
            "readmy_ticket_ownership": "UNKNOWN",
            "core_run_ticket_binding": "UNKNOWN",
            "signer_nonce_revocation": "UNKNOWN",
            "human_allow": False,
        },
        "authority_sources": {
            "schema": "aiops.portal.authority-sources.v1",
            "provenance": "PORTAL_CONTRACT_ONLY",
            "observed_at": None,
            "freshness": "UNKNOWN",
            "core_pg16_producer": "SOURCE_CONTRACT_ONLY_NOT_HUMAN_ACL",
            "idp_glpi_mapping": "NOT_ATTESTED",
            "glpi_native_readmy_ownership": "NOT_ATTESTED",
            "core_run_signer_nonce_revocation": "NOT_ATTESTED",
            "independent_proofs_verified": False,
            "human_allow": False,
        },
        "tenant_acl_qualified": False,
        "runtime_attested": False,
        "glpi_write_enabled": False,
        "live_remediation_authorized": False,
    }, status_code=503, headers=SECURITY)
