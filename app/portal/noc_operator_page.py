"""P0 #385: dedicated NOC operator surface; no implicit tenant authorization."""
import html
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse
from portal.acme_impact_read_model import build_acme_impact_read_model

router = APIRouter()
HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; connect-src 'self'; "
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"
    ),
}
PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NOC opérateur — ACME AIOps2</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#081521;color:#edf5fa;font:15px/1.55 system-ui,sans-serif}
main{max-width:1150px;margin:auto;padding:24px}nav{display:flex;flex-wrap:wrap;gap:16px}
a{color:#a6ddff}h1{font-size:clamp(1.5rem,4vw,2.5rem)}.panel{background:#102538;border:1px solid #38566d;border-radius:14px;padding:18px;margin:16px 0}
label{display:block;margin:10px 0 5px}input,select{background:#06111e;color:#fff;border:1px solid #7291a5;border-radius:8px;padding:10px;max-width:100%}
button{background:#236b99;color:#fff;border:1px solid #7cb9de;border-radius:8px;padding:10px;margin:10px 8px 10px 0}
button:focus-visible,input:focus-visible,select:focus-visible,a:focus-visible{outline:3px solid #f9d87b;outline-offset:3px}
table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #38566d;text-align:left}td{overflow-wrap:anywhere}
.status{color:#f9d87b;font-weight:700}.muted{color:#bed1dd}.table-wrap{overflow-x:auto}
@media(max-width:640px){main{padding:14px}td,th{padding:7px}}
</style></head><body><main>
<nav aria-label="Navigation opérateur"><a href="/">Cockpit</a><a href="/demo-center">DemoCenter</a><a href="/itsm">GLPI réel / droits humains</a>
<a href="/demo/explore-story">ACME Story (simulation)</a><a href="/demo/acme-impact">Impact Twin (simulation)</a></nav>
<h1>NOC opérateur — incidents SAN / Payments / ERP</h1>
<p class="muted">Lecture seule. Aucun incident, impact, ticket, diagnostic Analyst/Critic ni droit humain n'est déduit d'un HTTP 200.
Les sources sans ACL acteur+tenant vérifiée restent UNKNOWN / 503. Les actions LIVE sont interdites.</p>
<section class="panel"><h2>Source NOC et corrélation Core</h2>
<label for="noc-viewer-token">Jeton de lecture portail (non conservé)</label>
<input id="noc-viewer-token" type="password" autocomplete="off" spellcheck="false">
<button type="button" id="noc-load">Lire NOC</button><button type="button" id="noc-clear">Effacer</button>
<p id="noc-state" class="status" role="status" aria-live="polite">UNKNOWN — authentification et ACL non vérifiées</p>
<p id="noc-correlation" class="muted">Corrélation Core : NOT_ATTESTED</p>
</section>
<!-- SYNTHETIC_REFERENCE_SLOT -->
<section class="panel"><h2>File d'incidents</h2>
<label for="noc-filter">Filtre état</label><select id="noc-filter">
<option value="ALL">Tous</option><option value="OK">OK</option><option value="WARN">WARN</option>
<option value="CRIT">CRIT</option><option value="UNKNOWN">UNKNOWN</option></select>
<div class="table-wrap"><table><thead><tr><th scope="col">Incident / Run</th>
<th scope="col">État source</th><th scope="col">Provenance</th><th scope="col">Preuve / impact</th></tr></thead>
<tbody id="noc-rows"><tr><td colspan="4">UNKNOWN — aucun incident autorisé</td></tr></tbody></table></div>
</section>
<section class="panel"><h2>Diagnostic et limites</h2><p>Le modèle NOC signé n'est pas une attestation de panne SAN.
Le lien incident→Run exige une lecture Core indépendante et un contrôle ACL côté serveur.
Analyst/Critic doivent s'abstenir sans preuve ; SIM-GLPI n'est jamais un ticket humain.</p>
<p id="noc-diagnostic" role="status">NOC : NOT_VERIFIED · n8n login : NOT_VERIFIED · GLPI humain : NOT_VERIFIED</p></section>
</main><script src="/assets/noc-operator.js" defer></script></body></html>"""



def _synthetic_reference() -> str:
    """Reuse the validated local Twin fixture, never an authorized NOC incident.

    This six-CI reference is NOT the independent PG16 migration-019 9/8 graph.
    The real incident queue and actor/tenant ACL remain UNKNOWN.
    """
    unavailable = (
        '<section class="panel" id="noc-synthetic-reference" '
        'aria-label="Référence SAN synthétique">'
        '<h2>Référence SAN → Payments — simulation</h2>'
        '<p id="noc-synthetic-status">UNKNOWN — fixture locale absente ou invalide ; '
        'aucune observation runtime.</p></section>'
    )
    try:
        model = build_acme_impact_read_model()
        if (model.get("schema") != "aiops.synthetic-impact-read-model.v1"
                or model.get("provenance") != "SIMULATED_TARGET"
                or model.get("evidence_source") != "LOCAL_SYNTHETIC_FIXTURE"
                or model.get("runtime_attested") is not False
                or model.get("live_remediation_authorized") is not False
                or model.get("ticket_id") is not None
                or model.get("source_artifact") != "app/portal/acme-fixtures.json"
                or not isinstance(model.get("impact_path"), list)
                or not all(isinstance(node, str) for node in model["impact_path"])):
            return unavailable
        escape = lambda value: html.escape(str(value), quote=True)
        path = " → ".join(model["impact_path"])
        return (
            '<section class="panel" id="noc-synthetic-reference" '
            'aria-label="Référence SAN synthétique">'
            '<h2>Référence SAN → Payments — simulation</h2>'
            '<p id="noc-synthetic-status">SYNTHETIC_REFERENCE_ONLY · '
            'LOCAL_SYNTHETIC_FIXTURE · aucun incident NOC autorisé.</p>'
            '<p>Cette référence locale comporte ' + escape(model["ci_count"]) +
            ' CI. Elle ne représente PAS le graphe PG16 ACME-TEST migration 019 '
            '(9 nœuds / 8 arêtes), qui exige une preuve de provenance distincte.</p>'
            '<p id="noc-synthetic-path">Chemin calculé : ' + escape(path) + '</p>'
            '<p>Incidents fictifs : ' + escape(model["incident_id"]) + ' → ' +
            escape(model["impact_incident_id"]) + '</p>'
            '<p id="noc-synthetic-source">Source : ' +
            escape(model["source_artifact"]) + ' · SHA-256 : ' +
            escape(model["source_sha256"]) + '</p>'
            '<p>Analyst/Critic : NOT_ATTESTED · impact ERP : UNKNOWN · '
            'SIM-GLPI : pas de ticket humain · Worker : NO LIVE EFFECT.</p>'
            '<p><a href="/demo/acme-impact">Ouvrir le graphe synthétique</a> · '
            '<a href="/demo-center">Retour DemoCenter</a></p></section>'
        )
    except (OSError, ValueError, UnicodeError, TypeError, KeyError, AttributeError):
        return unavailable


@router.get("/noc", response_class=HTMLResponse)
def noc_operator_page():
    return HTMLResponse(PAGE.replace("<!-- SYNTHETIC_REFERENCE_SLOT -->",
                                     _synthetic_reference()), headers=HEADERS)


@router.get("/assets/noc-operator.js")
def noc_operator_script():
    return FileResponse(Path(__file__).with_name("noc_operator_client.js"),
                        media_type="application/javascript", headers=HEADERS)
