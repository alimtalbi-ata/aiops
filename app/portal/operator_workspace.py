"""AIOps operator workspace: pedagogic entrypoint, no client bearer prompt.

Public content is a navigation shell. The only scenario data requested by JS
is the explicitly local, synthetic impact fixture; no real Run/tenant data.
Authentication is via the existing server-managed OIDC session, never by
typing a shared service token into a web form. No new authorization.
"""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()
ROOT = Path(__file__).parent
SECURITY = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOps2 · Centre de pilotage</title>
<link rel="stylesheet" href="/assets/operator-workspace.css">
<script src="/assets/operator-workspace.js" defer></script>
</head><body>
<a class="skip" href="#main">Aller au contenu</a>
<div class="app-layout">
<aside class="sidebar" aria-label="Navigation principale">
  <a class="brand" href="/"><span class="brand-symbol" aria-hidden="true">A<span>·</span></span>
    <span><strong>AIOps<span class="brand-accent">2</span></strong><small>OPS INTELLIGENCE</small></span></a>
  <div class="side-context"><span class="signal" aria-hidden="true"></span>
    ENVIRONNEMENT DE DÉMONSTRATION</div>
  <p class="side-label">ESPACE OPÉRATEUR</p>
  <nav class="side-nav" aria-label="Sections de cet espace">
    <a href="#overview" data-view="overview" aria-current="page"><span aria-hidden="true">◫</span> Vue d'ensemble</a>
    <a href="#journey" data-view="journey"><span aria-hidden="true">◇</span> Parcours SAN → Payments</a>
    <a href="#runs" data-view="runs"><span aria-hidden="true">≡</span> Incidents et Runs</a>
    <a href="#connections" data-view="connections"><span aria-hidden="true">⌘</span> Accès et connexions</a>
  </nav>
  <p class="side-label">OUTILS DU PORTAIL</p>
  <nav class="side-nav" aria-label="Fonctions existantes">
    <a href="/noc"><span aria-hidden="true">▤</span> Cockpit NOC</a>
    <a href="/demo-center"><span aria-hidden="true">▣</span> DemoCenter / Vidéo</a>
    <a href="/demo-studio"><span aria-hidden="true">◷</span> Demo Studio V2</a>
    <a href="/demo/explore-story"><span aria-hidden="true">▷</span> Explore / Story</a>
    <a href="/demo/acme-impact"><span aria-hidden="true">⌁</span> Digital Twin</a>
    <a href="/itsm"><span aria-hidden="true">▥</span> GLPI / ITSM</a>
  </nav>
  <div class="side-bottom"><span>ACME-TEST · Données synthétiques</span>
    <small>Actions LIVE désactivées</small></div>
</aside>
<div class="main-shell">
<header class="topbar">
  <div class="crumb">Centre de pilotage <span aria-hidden="true">/</span> <strong id="active-view">Vue d'ensemble</strong></div>
  <div class="top-actions"><span class="top-tag"><span class="top-dot" aria-hidden="true"></span> DEMO / SANS EFFET</span>
    <a class="top-help" href="#connections" data-view="connections">État des accès</a></div>
</header>
<main id="main" tabindex="-1">
<section class="view" id="overview" data-panel="overview" aria-labelledby="overview-heading">
  <div class="intro"><span class="eyebrow">PLATEFORME AIOPS · V28</span>
    <h1 id="overview-heading">Comprendre l'incident.<br><span>Décider avec des preuves.</span></h1>
    <p>De la dégradation d'un chemin SAN à l'impact sur Payments : un parcours guidé pour comprendre ce qui est connu, ce qui reste à vérifier et pourquoi aucune action LIVE n'est lancée.</p>
    <div class="hero-actions"><a class="button primary" href="#journey" data-view="journey">Explorer le scénario <span aria-hidden="true">→</span></a>
      <a class="button ghost" href="/demo-center">Ouvrir le DemoCenter</a></div>
    <div class="hero-decoration" aria-hidden="true"><span>SAN</span><i></i><span>VIRTUALISATION</span><i></i><span>PAYMENTS</span></div>
  </div>
  <div class="section-heading"><div><span class="eyebrow">LECTURE GUIDÉE</span><h2>Le scénario en un regard</h2></div>
    <button type="button" class="text-button" id="refresh-fixture">Actualiser les données de démonstration <span aria-hidden="true">↻</span></button></div>
  <p class="source-alert" role="status" id="fixture-status" aria-live="polite">Chargement du jeu de données synthétique local…</p>
  <div class="metric-grid" aria-label="Indicateurs du scénario synthétique">
    <article class="metric"><span class="metric-label">Incident déclencheur</span><strong>SAN <em class="red">P1</em></strong><small>Dégradation illustrée, non observée en production</small></article>
    <article class="metric"><span class="metric-label">Service étudié</span><strong>Payments <em class="amber">P2</em></strong><small>Impact hypothétique selon les dépendances</small></article>
    <article class="metric"><span class="metric-label">CI du modèle local</span><strong id="ci-count">—</strong><small>Éléments déclarés dans la fixture</small></article>
    <article class="metric"><span class="metric-label">Preuves runtime</span><strong class="small-value">Non attestées</strong><small>Aucune observation réelle revendiquée</small></article>
  </div>
  <div class="split">
    <section class="surface" aria-labelledby="path-heading">
      <div class="panel-top"><div><span class="eyebrow">DIGITAL TWIN · SYNTHÉTIQUE</span><h2 id="path-heading">D'où vient l'impact ?</h2></div>
        <a class="inline-link" href="/demo/acme-impact">Graphe détaillé →</a></div>
      <p class="lead">Le graphe décrit une dépendance possible, pas une panne réelle certifiée.</p>
      <ol class="impact-path" id="impact-path"><li class="empty-step">Graphe non chargé</li></ol>
      <div class="source-footer"><span>Provenance : <strong id="fixture-provenance">Non vérifiée</strong></span><span id="fixture-hash">Empreinte indisponible</span></div>
    </section>
    <section class="surface insight" aria-labelledby="guide-heading">
      <span class="eyebrow">EXPLICATION OPÉRATEUR</span><h2 id="guide-heading">Ce qu'il faut comprendre</h2>
      <div class="insight-item"><span class="insight-icon red-bg">01</span><div><strong>Détecter le signal</strong><p>Un défaut de fabric SAN ne prouve pas seul une dégradation de Payments.</p></div></div>
      <div class="insight-item"><span class="insight-icon blue-bg">02</span><div><strong>Suivre les dépendances</strong><p>Le Twin relie les équipements au service métier, en conservant la provenance.</p></div></div>
      <div class="insight-item"><span class="insight-icon amber-bg">03</span><div><strong>Vérifier avant d'agir</strong><p>Sans preuve indépendante, Analyst/Critic et Policy doivent s'abstenir d'autoriser une remédiation.</p></div></div>
      <a class="inline-link" href="#journey" data-view="journey">Voir les étapes du traitement →</a>
    </section>
  </div>
  <div class="section-heading"><div><span class="eyebrow">RACCOURCIS OPÉRATIONNELS</span><h2>Aller plus loin</h2></div></div>
  <div class="shortcut-grid">
    <a class="shortcut" href="/noc"><span class="shortcut-icon">▤</span><strong>NOC</strong><small>Événements, corrélation et provenance</small><span class="shortcut-arrow">↗</span></a>
    <a class="shortcut" href="/demo-studio"><span class="shortcut-icon">◷</span><strong>Studio V2</strong><small>Chronologie historique et décisions</small><span class="shortcut-arrow">↗</span></a>
    <a class="shortcut" href="/demo-center"><span class="shortcut-icon">▣</span><strong>Vidéo</strong><small>Parcours et capture locale avec consentement</small><span class="shortcut-arrow">↗</span></a>
    <a class="shortcut" href="/itsm"><span class="shortcut-icon">▥</span><strong>GLPI</strong><small>Tickets et contrôle des droits humains</small><span class="shortcut-arrow">↗</span></a>
  </div>
</section>
<section class="view" id="journey" data-panel="journey" aria-labelledby="journey-heading" hidden>
  <span class="eyebrow">ACME / SAN → PAYMENTS</span><h1 id="journey-heading" class="view-title">Du signal à la décision.</h1>
  <p class="view-lead">Une histoire métier en cinq phases. Chaque étape distingue les fonctions disponibles des preuves manquantes.</p>
  <div class="notice"><strong>Mode référence synthétique.</strong> Sélectionner un scénario ne l'exécute pas. Les huit hypothèses ne sont pas huit simulations déjà qualifiées.</div>
  <div class="surface scenario-picker"><label for="scenario-select">Hypothèse à découvrir</label>
    <select id="scenario-select"><option value="fc">Dégradation d'un lien FC / SFP</option><option value="multipath">Perte d'un chemin multipath RHEL</option><option value="controller">Basculement de contrôleur Dell / Pure</option><option value="neighbor">Contention / noisy neighbor</option><option value="replication">Retard de réplication</option><option value="capacity">Saturation de capacité</option><option value="change">Changement SAN</option><option value="storm">Tempête de faux positifs</option></select>
    <p id="scenario-description" role="status">Le scénario de référence SAN → Payments est chargé depuis la fixture locale.</p>
  </div>
  <div class="journey-grid">
    <article class="step-card"><span>01 · DÉTECTER</span><h2>Un signal SAN apparaît</h2><p>Conserver l'origine, les horodatages et le CI. Vérifier si le signal est authentifié.</p><a href="/noc">Voir le NOC →</a></article>
    <article class="step-card"><span>02 · COMPRENDRE</span><h2>Quel service dépend du SAN ?</h2><p>Suivre la topologie et discuter les chemins redondants avant de déclarer l'impact.</p><a href="/demo/acme-impact">Explorer le Twin →</a></article>
    <article class="step-card"><span>03 · ANALYSER</span><h2>Que disent les preuves ?</h2><p>Examiner les hypothèses Analyst/Critic ; une source contradictoire impose l'abstention.</p><a href="/demo-studio">Ouvrir le Studio V2 →</a></article>
    <article class="step-card"><span>04 · DÉCIDER</span><h2>Qui peut autoriser quoi ?</h2><p>Policy et HITL séparent recommandation, approbation simulée et permission humaine.</p><a href="/itsm">Contrôler l'ITSM →</a></article>
    <article class="step-card"><span>05 · VÉRIFIER</span><h2>Le résultat est-il prouvé ?</h2><p>Worker sans effet, lecture indépendante, puis Core tranche sur l'état du Run.</p><a href="/demo-center">Revoir / enregistrer →</a></article>
  </div>
</section>
<section class="view" id="runs" data-panel="runs" aria-labelledby="runs-heading" hidden>
  <span class="eyebrow">INCIDENTS &amp; RUNS</span><h1 id="runs-heading" class="view-title">Une seule chronologie. Une source de vérité.</h1>
  <p class="view-lead">Les données opérationnelles sont protégées par les droits acteur et tenant. Une session d'entreprise ne suffit pas, à elle seule, à autoriser un Run.</p>
  <div class="surface empty-real"><span aria-hidden="true" class="empty-glyph">◎</span>
    <h2>Liste d'incidents réels non disponible</h2>
    <p>Le portail ne peut pas encore attester la lecture Core/GLPI pour cet utilisateur. Nous n'affichons ni fausses métriques, ni faux tickets, ni résultats empruntés au scénario synthétique.</p>
    <a class="button primary" href="#connections" data-view="connections">Comprendre l'accès requis →</a>
    <a class="button ghost-dark" href="/demo-center">Explorer la démonstration</a>
  </div>
  <section class="surface compact"><h2>Ce qu'apportera le parcours autorisé</h2><p>Incident P1, Run Core, état Temporal, preuve de fraîcheur, impact métier, analyse et critique, proposition Policy, décision HITL, reçu Worker et vérification finale — tous reliés par les mêmes identifiants.</p></section>
</section>
<section class="view" id="connections" data-panel="connections" aria-labelledby="connections-heading" hidden>
  <span class="eyebrow">IDENTITÉ ET INTÉGRATIONS</span><h1 id="connections-heading" class="view-title">Vos accès, sans jeton manuel.</h1>
  <p class="view-lead">Le portail doit utiliser une session d'entreprise et des autorisations vérifiées côté serveur. Il ne demande plus de copier un secret technique dans un formulaire.</p>
  <div class="split">
    <section class="surface"><h2>Session du portail</h2><p id="session-status" role="status">Vérification de la session…</p>
      <p class="muted">Une session OIDC authentifie une identité ; l'accès aux incidents exige en plus une autorisation Core/GLPI acteur + tenant.</p>
      <div class="stack-actions"><a class="button primary" href="/auth/oidc/login" id="sso-link">Se connecter avec l'entreprise →</a>
      <button type="button" class="button ghost-dark" id="check-session">Revérifier</button></div>
      <p id="secure-origin-hint" class="muted"></p>
    </section>
    <section class="surface"><h2>Accès métiers</h2><ul class="connection-list">
      <li><span>Core / Run</span><strong>ACL indépendante requise</strong></li>
      <li><span>GLPI</span><strong>Profil, entité et READMY à vérifier</strong></li>
      <li><span>n8n</span><strong>Connexion non attestée</strong></li>
      <li><span>Monitoring NOC</span><strong>Source et fraîcheur à qualifier</strong></li>
    </ul><p class="muted">Ces mentions sont des limites observées du produit, pas des incidents réels.</p></section>
  </div>
  <div class="notice"><strong>Pourquoi l'ancienne page demandait des jetons :</strong> elle exposait directement des contrats d'API internes. La nouvelle interface retire cette manipulation côté opérateur ; les droits humains et la connectivité SSO doivent néanmoins être implémentés et testés sur Debian avant d'afficher de vraies données.</div>
</section>
<footer>ACME AIOps2 · Vue pédagogique en lecture seule · Aucun ticket GLPI ni effet LIVE généré par cette page.</footer>
</main></div></div>
</body></html>"""


@router.get("/", response_class=HTMLResponse, name="operator_workspace_home")
@router.get("/workspace", response_class=HTMLResponse, name="operator_workspace")
@router.get("/runs", response_class=HTMLResponse, name="operator_workspace_runs")
def workspace():
    """Anonymous shell with labelled synthetic reference, never a Run inventory."""
    return HTMLResponse(PAGE, headers=SECURITY)


@router.get("/assets/operator-workspace.css", name="operator_workspace_css")
def workspace_css():
    return FileResponse(ROOT / "operator_workspace.css",
                        media_type="text/css", headers=SECURITY)


@router.get("/assets/operator-workspace.js", name="operator_workspace_js")
def workspace_js():
    return FileResponse(ROOT / "operator_workspace.js",
                        media_type="application/javascript", headers=SECURITY)
