"""DemoCenter: recover the existing ACME portal journey, never fabricate runtime evidence.

Only links to already-mounted Explore/Story, Twin impact, NOC and ITSM routes.
The eight P1 SAN labels are a *catalogue*, not eight executable simulations.
The recorder runs exclusively in the user's browser; nothing is uploaded.
"""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse

router = APIRouter()

HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "display-capture=(self)",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
        "connect-src 'none'; media-src blob:; img-src 'none'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DemoCenter ACME — SAN / Digital Twin</title>
<style>
body{margin:0;background:#081522;color:#ecf4ff;font:15px/1.5 system-ui,sans-serif}
main{max-width:1080px;margin:auto;padding:22px}
a{color:#9bdaff}a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #ffdb84;outline-offset:3px}
nav{display:flex;flex-wrap:wrap;gap:14px}
.panel{background:#10243a;border:1px solid #315773;border-radius:13px;padding:18px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
button{background:#237cbd;color:#fff;border:0;border-radius:8px;padding:11px 16px;margin:4px 8px 4px 0;cursor:pointer}
button:disabled{background:#526575;cursor:not-allowed}
select{background:#091a2a;color:white;padding:10px;border:1px solid #9bb8ca;max-width:100%;width:100%}
.muted{color:#b2c6d6}.warning{border-left:4px solid #ffce70;padding-left:12px}
video{width:100%;max-height:380px;background:#030c13}
#recording-status,#scenario-status{white-space:pre-wrap}
</style></head><body><main>
<nav aria-label="Navigation portail">
<a href="/">Portail :7777</a><a href="/noc">NOC</a>
<a href="/demo/acme-impact">Twin SAN → Payments (fixture)</a>
<a href="/demo/explore-story">Explore / Story</a><a href="/demo-studio">Demo Studio V2 historique</a><a href="/itsm">ITSM / GLPI</a>
</nav>
<h1>DemoCenter · SAN / ACME</h1>
<p class="warning"><strong>SIMULATION_ONLY / NO LIVE EFFECT.</strong>
Ce centre assemble les vues historiques déjà montées. Il ne déclenche ni incident,
ni approbation humaine, ni exécution Worker, ni ticket GLPI réel.</p>
<section class="panel" aria-labelledby="scenario-title">
<h2 id="scenario-title">Sélection de scénario SAN</h2>
<label for="san-scenario">Hypothèses P1 — catalogue non exécutable ici</label>
<select id="san-scenario">
<option value="fc">FC SFP / perte de lien fabric</option>
<option value="multipath">Multipath RHEL / chemin dégradé</option>
<option value="controller">Contrôleur Dell / Pure</option>
<option value="neighbor">Noisy neighbor / contention</option>
<option value="replication">Réplication / retard</option>
<option value="capacity">Capacité / seuil</option>
<option value="change">Changement SAN</option>
<option value="storm">Tempête de faux positifs</option>
</select>
<p id="scenario-status" role="status">CATALOG_ONLY — Analyst/Critic NOT_ATTESTED ; aucune observation SAN LIVE.</p>
<p class="muted">Le catalogue P1 #366 n'est pas intégré à ce portail.
La sélection ne modifie pas la fixture ni ne prétend lancer un scénario.</p>
</section>
<div class="grid">
<section class="panel"><h2>1 · Twin & impact</h2>
<p>Ouvrir le graphe synthétique SAN → Payments et sa provenance SHA256.
La redondance, ERP et les effets métier réels restent UNKNOWN sans preuves.</p>
<a href="/demo/acme-impact">Voir le graphe existant</a></section>
<section class="panel"><h2>2 · Explorer / rejouer</h2>
<p>Parcours Explore/Story déjà présent, avec jeton viewer éphémère,
checkpoints MISSING et commandes de lecture sans effet.</p>
<a href="/demo/explore-story">Ouvrir Explore / Story</a></section>
<section class="panel"><h2>3 · NOC / GLPI</h2>
<p>Vues existantes de corrélation et ITSM, sous contrôle ACL.
Incident, Analyst/Critic, Policy, SIM-GLPI et readback : UNKNOWN
tant que les preuves de même Run et tenant ne sont pas qualifiées.</p>
<a href="/noc">Ouvrir NOC</a> · <a href="/itsm">Ouvrir ITSM</a></section>
</div>
<section class="panel" aria-labelledby="recording-workflow-title">
<h2 id="recording-workflow-title">Enregistrer la démonstration entre plusieurs pages</h2>
<p>Une capture démarrée dans cet onglet s'arrête lorsque vous quittez la page.
Pour filmer le parcours Twin → NOC → Demo Studio sans perdre la vidéo,
ouvrez le <strong>même enregistreur historique</strong> dans un second onglet
et gardez ce second onglet ouvert pendant la navigation.</p>
<p><a id="recorder-station-link" href="/demo-center/recorder" target="_blank" rel="noopener noreferrer">Ouvrir le poste de capture dans un nouvel onglet</a></p>
<p class="muted">Dans le poste de capture : consentir, démarrer, puis choisir
explicitement l'onglet de démonstration dans le sélecteur du navigateur.
Revenir au premier onglet pour naviguer ; arrêter, relire et exporter
depuis le poste de capture. Ne pas capturer de secrets. Aucun upload.</p>
</section>
<section class="panel" aria-labelledby="recorder-title">
<h2 id="recorder-title">Capture vidéo locale · enregistreur navigateur</h2>
<p class="warning">La capture peut inclure tout ce qui est visible dans la fenêtre
ou l'écran choisi, y compris des secrets. Masquer les identifiants et jetons
avant de commencer. Aucun masquage automatique n'est garanti.</p>
<p>Capture uniquement après autorisation explicite du navigateur.
Aucun envoi réseau, aucune sauvegarde serveur. L'export local est manuel.
HTTPS ou localhost est nécessaire pour autoriser le partage d'écran.</p>
<label><input type="checkbox" id="recording-consent">
J'ai masqué les informations sensibles et je consens à une capture locale.</label>
<p><button type="button" id="record-start" disabled>Démarrer la capture</button>
<button type="button" id="record-stop" disabled>Arrêter</button>
<button type="button" id="record-clear">Effacer la capture locale</button></p>
<p id="recording-status" role="status" aria-live="polite">NOT_STARTED — aucune vidéo.</p>
<video id="record-preview" controls playsinline aria-label="Relecture vidéo locale"></video>
<p><a id="record-download" hidden>Télécharger la vidéo locale</a></p>
<p class="muted">L'assemblage historique PNG → MP4 (#43) est un outil de preuve
hors ligne distinct. Cette capture navigateur n'est ni une attestation runtime
ni un reçu E2E Debian.</p>
</section>
</main><script src="/assets/demo-center-recorder.js" defer></script></body></html>"""


@router.get("/demo-center", response_class=HTMLResponse)
def demo_center_page():
    """Public navigation shell only: zero Core/Twin/GLPI/n8n reads or writes."""
    return HTMLResponse(PAGE, headers=HEADERS)



@router.get("/demo-center/recorder", response_class=HTMLResponse)
def demo_center_recorder_station():
    """Reuse the exact recorder page in a separate tab for cross-route capture.

    Browser capture permission is still user-mediated; no backend access or
    persistence is introduced. A station tab must stay open during navigation.
    """
    station = PAGE.replace(
        "<title>DemoCenter ACME — SAN / Digital Twin</title>",
        "<title>Poste de capture locale — DemoCenter ACME</title>",
    ).replace(
        "<h1>DemoCenter · SAN / ACME</h1>",
        '<h1>Poste de capture locale · SAN / ACME</h1>'
        '<p class="warning"><strong>LOCAL_ONLY / NO LIVE EFFECT.</strong> '
        'Gardez cet onglet ouvert ; choisissez l’onglet de démonstration '
        'dans la permission navigateur, puis naviguez dans cet autre onglet. '
        'La vidéo reste locale et non attestée.</p>',
    )
    return HTMLResponse(station, headers=HEADERS)


@router.get("/assets/demo-center-recorder.js")
def demo_center_script():
    return FileResponse(
        Path(__file__).with_name("demo_center_recorder.js"),
        media_type="application/javascript",
        headers=HEADERS,
    )


@router.get("/demo-studio", response_class=HTMLResponse)
def historical_demo_studio():
    """Recover the original Demo V2 renderer without unauthorised Core reads.

    The existing exact-Run /runs/{rid} endpoint remains the sole source
    of tenant-authorized Run detail. No fixture can impersonate a Run.
    """
    from portal.demo_v2 import render_demo_v2
    from portal.ui_theme import THEME
    body = render_demo_v2(
        {"run": {"status": "INCONNU"}},
        {"status": "UNKNOWN", "error_type": "Unauthorized"},
        {"status": "UNKNOWN"},
    )
    page = (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Demo Studio V2 historique — ACME</title>'
        '<style>' + THEME + '</style></head><body>'
        '<main><nav aria-label="Parcours Demo Studio">'
        '<a href="/demo-center">DemoCenter</a> · '
        '<a href="/demo/acme-impact">Twin SAN → Payments synthétique</a> · '
        '<a href="/noc">NOC</a> · <a href="/itsm">ITSM</a></nav>'
        '<h1>Demo Studio V2 — rendu historique restauré</h1>'
        '<p><strong>SYNTHETIC_REFERENCE_ONLY / NO LIVE EFFECT.</strong> '
        'Aucun Run, incident, événement, ticket, Analyst/Critic ou décision '
        'Policy n’est attesté par cette page anonyme.</p>'
        '<p>Pour une lecture de Run réel, utiliser le parcours existant '
        '<code>/runs/{rid}</code> avec une autorisation serveur acteur/tenant '
        'et un identifiant exact. Sans ACL, le résultat reste UNKNOWN.</p>'
        + body + '</main></body></html>'
    )
    return HTMLResponse(page, headers=HEADERS)
