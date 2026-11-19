"""Static presenter-first Demo Studio: synthetic-only, no fixture or upstream I/O."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
HEADERS = {
    "Cache-Control": "no-store", "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    ),
}
PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOps · Demo Studio</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#071321;color:#edf5fb;font:16px/1.55 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:28px}a{color:#8ed4ff}
a:focus-visible{outline:3px solid #ffda7a;outline-offset:3px}
header{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
.eyebrow,.time{color:#ffda7a;font-weight:700}.eyebrow{letter-spacing:.08em}
h1{font-size:clamp(2rem,5vw,3.4rem);line-height:1.08;margin:.35em 0}
.lead{color:#c1d2df;max-width:760px}.notice{border:1px solid #9c7535;background:#2b2418;padding:14px 18px;border-radius:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.card{background:#10263b;border:1px solid #2c4c65;border-radius:14px;padding:18px}
.card h2{margin:0 0 8px;font-size:1.15rem}blockquote{margin:10px 0 0;padding-left:14px;border-left:3px solid #4e7896;color:#d4e2ec}
ol{padding-left:22px}li{padding:5px 0}footer{margin-top:28px;color:#a8bdcc;font-size:.92rem}
@media print{body{background:white;color:#111}.card,.notice{background:white;color:#111;border:1px solid #777}a{color:#064d78}.eyebrow,.time{color:#6a4a00}}
</style></head><body><main>
<header><a href="/">← Operations Command Center</a><span class="eyebrow">DEMO STUDIO · SYNTHETIC ONLY</span></header>
<h1>ACME · Incident majeur SAN → Payments</h1>
<p class="lead">Parcours de démonstration de cinq minutes : détection, impact métier,
investigation guidée et gouvernance. Les vues utilisent des contrats de scénario
synthétiques ; elles ne prouvent pas une connexion aux outils client.</p>
<section class="notice" role="note"><strong>SIMULATION uniquement.</strong>
Aucun incident ou ticket réel, aucune lecture GLPI/Core, aucune commande,
aucune approbation réelle et aucune remédiation LIVE. Les preuves non disponibles
restent UNKNOWN ou MISSING.</section>
<h2>Parcours guidé · 5 minutes</h2><section class="grid" aria-label="Étapes de démonstration">
<article class="card"><div class="time">00:00 · 45 s</div><h2>1. Contexte métier</h2>
<p>ACME, Payments et la dégradation SAN : expliquer l'impact avant de parler d'action.</p>
<blockquote>« Nous partons d'un incident P1 synthétique. L'objectif est de comprendre l'impact. »</blockquote></article>
<article class="card"><div class="time">00:45 · 60 s</div><h2>2. Visualiser l'impact</h2>
<p>Présenter le chemin SAN → stockage → Payments et distinguer les relations de fixture des dépendances runtime vérifiées.</p>
<blockquote>« Le graphe raconte le chemin attendu ; une relation non prouvée reste UNKNOWN. »</blockquote>
<a href="/demo/acme-impact">Ouvrir ACME Impact →</a></article>
<article class="card"><div class="time">01:45 · 90 s</div><h2>3. Explorer les checkpoints</h2>
<p>Parcourir Detect, Correlate, Enrich, Analyze, Ticket, Approve, Simulate et Verify. Comparer Explore et Story.</p>
<blockquote>« MISSING ne signifie pas que l'action a réussi. Chaque étape a son contrat de preuve. »</blockquote>
<a href="/demo/explore-story">Ouvrir Explore / Story →</a></article>
<article class="card"><div class="time">03:15 · 60 s</div><h2>4. Gouvernance ITSM</h2>
<p>Montrer le point de passage GLPI et les champs UNKNOWN tant que l'ACL acteur/tenant et le mapping ticket↔Run ne sont pas qualifiés.</p>
<blockquote>« Recommandation, approbation, effet et vérification sont quatre choses distinctes. »</blockquote>
<a href="/itsm">Ouvrir le handoff ITSM →</a></article>
<article class="card"><div class="time">04:15 · 45 s</div><h2>5. Conclusion honnête</h2>
<p>Résumer ce que démontre le scénario et les intégrations restant à qualifier : identité/tenant, GLPI, NOC et exécution isolée.</p>
<blockquote>« Nous démontrons le parcours et ses garde-fous, pas une remédiation de production. »</blockquote>
<a href="/">Retour au cockpit →</a></article>
</section>
<h2>Préparation avant le rendez-vous</h2><ol>
<li>Ouvrir cette page et les deux vues ACME dans des onglets séparés.</li>
<li>Utiliser un environnement de démonstration autorisé ; ne pas saisir de jeton de production.</li>
<li>Garder le marqueur SYNTHETIC / SIMULATION visible pendant le partage d'écran.</li>
<li>Ne pas présenter GLPI, NOC, Grafana ou Core comme connectés sans preuve fraîche et autorisée.</li>
<li>Si une vue affiche UNKNOWN, expliquer la dépendance manquante au lieu de masquer l'état.</li>
</ol><footer>Contenu statique · aucun appel réseau ni stockage navigateur · aucun effet sur les services, tickets ou Runs.</footer>
</main></body></html>"""

@router.get("/demo/studio", response_class=HTMLResponse)
def demo_studio_page():
    """Serve the presenter aid without reading fixtures or contacting services."""
    return HTMLResponse(PAGE, headers=HEADERS)
