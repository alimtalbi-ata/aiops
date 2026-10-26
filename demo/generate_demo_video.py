"""Generate a complete, deterministic AIOps demo video from synthetic STAR scenes.

Requires Playwright + Chromium and ffmpeg. espeak-ng is optional (French narration).
No application endpoints are contacted. The output is explicitly marked SIMULATION.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from html import escape

SCENES = [
    ("01", "DÉTECTION", "Une alerte de perte de redondance SAN est simulée.", "GRAFANA", "ALERTE P1", "Détection", "Événement synthétique — aucun runtime interrogé."),
    ("02", "CORRÉLATION", "Les événements Fibre Channel et multipath sont rapprochés dans une chronologie fictive.", "N8N", "CORRÉLATION", "Corrélation", "Flux illustratif — aucune exécution n8n revendiquée."),
    ("03", "CONTEXTE & CMDB", "Le scénario présente les dépendances applicatives et les ressources supposées impactées.", "CMDB", "IMPACT À ÉVALUER", "Contexte", "Dépendances de démonstration — non vérifiées en production."),
    ("04", "ANALYSE IA", "Une hypothèse de cause est confrontée à une contre-analyse critique.", "DGX / IA", "HYPOTHÈSE", "Analyse et critique", "Texte narratif synthétique — aucune attestation DGX."),
    ("05", "INCIDENT GLPI", "La démonstration montre les informations qu’un ticket d’incident devrait contenir.", "GLPI", "TICKET ILLUSTRATIF", "Ticket", "Aucun ticket GLPI n’est créé ni modifié."),
    ("06", "VALIDATION HUMAINE", "La politique impose une validation explicite avant toute action sensible.", "HITL / POLICY", "APPROBATION REQUISE", "Décision humaine", "Aucune approbation réelle n’est demandée ou enregistrée."),
    ("07", "REMÉDIATION SIMULÉE", "Une action de remédiation fictive est présentée sans envoyer de commande.", "SIMULATEUR", "DRY-RUN", "Remédiation", "Aucune commande ni modification de production."),
    ("08", "VÉRIFICATION", "Les indicateurs avant et après sont comparés à titre illustratif.", "OBSERVABILITÉ", "RÉSULTAT SIMULÉ", "Vérification", "Aucune restauration réelle n’est affirmée."),
    ("09", "BILAN & PREUVES", "Le bilan distingue les éléments simulés, les preuves absentes et les qualifications restantes.", "EVIDENCE CENTER", "SIMULATION — NON LIVE", "Bilan", "Les captures ne constituent pas une preuve de runtime."),
]
WIDTH, HEIGHT = 1920, 1080
DURATION = 8

def scenes_for(scenario: str) -> list[tuple[str, ...]]:
    if scenario == "SAN_FABRIC_P1":
        return list(SCENES)
    if scenario != "PAYMENTS_P2":
        raise ValueError(f"Scénario inconnu : {scenario}")
    replacements = {
        0: ("01", "DÉGRADATION PAYMENTS", "Une hausse synthétique de latence et d'erreurs Payments est présentée comme incident P2.", "GRAFANA", "ALERTE P2", "Détection", "Événement synthétique — aucun runtime interrogé."),
        1: ("02", "CORRÉLATION DES SIGNAUX", "La chronologie fictive rapproche latence, erreurs applicatives et événements d'infrastructure.", "N8N", "CORRÉLATION P2", "Corrélation", "Flux illustratif — aucune exécution n8n revendiquée."),
        2: ("03", "CONTEXTE PAYMENTS", "Le scénario expose les dépendances Payments et les pistes stockage ou applicatives à départager.", "CMDB", "IMPACT À ÉVALUER", "Contexte", "Dépendances de démonstration — non vérifiées en production."),
        3: ("04", "HYPOTHÈSES & CRITIQUE", "L'analyse compare des hypothèses de cause sans présenter de diagnostic réel ni de réponse DGX attestée.", "DGX / IA", "HYPOTHÈSES P2", "Analyse et critique", "Texte narratif synthétique — aucune attestation DGX."),
        6: ("07", "TEST DE REMÉDIATION SIMULÉ", "Une action fictive de diagnostic et de remédiation est présentée sans envoyer de commande.", "SIMULATEUR", "DRY-RUN P2", "Remédiation", "Aucune commande ni modification de production."),
        7: ("08", "COMPARAISON DES SLO", "Les valeurs illustratives avant et après sont comparées sans supposer un retour à la normale.", "OBSERVABILITÉ", "RÉSULTAT SIMULÉ", "Vérification", "Aucune restauration réelle n’est affirmée."),
    }
    return [replacements.get(i, scene) for i, scene in enumerate(SCENES)]


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Commande requise introuvable : {name}")
    return path


def scene_html(scene: tuple[str, ...], index: int, total: int) -> str:
    number, title, narration, system, status, phase, disclaimer = scene
    # A purpose-built, browser-rendered dashboard view per scene. These are
    # illustrative snapshots, never represented as captures from live services.
    side_items = [
        ("01", "Vue NOC", index == 0),
        ("02", "Corrélation", index == 1),
        ("03", "Topologie", index == 2),
        ("04", "Analyse IA", index == 3),
        ("05", "Incidents", index == 4),
        ("06", "Validation HITL", index == 5),
        ("07", "Remédiation", index == 6),
        ("08", "Vérification", index == 7),
        ("09", "Centre de preuves", index == 8),
    ]
    nav = "".join(
        f'<div class="navitem {"active" if active else ""}"><span class="navnum">{n}</span>{escape(label)}</div>'
        for n, label, active in side_items
    )
    visual = _scene_visual(index)
    progress = int((index + 1) / total * 100)
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width={WIDTH},initial-scale=1">
<title>AIOps Demo Center — {escape(title)}</title>
<style>
*{{box-sizing:border-box}}html,body{{margin:0;width:{WIDTH}px;height:{HEIGHT}px;overflow:hidden}}
:root{{--bg:#07111f;--panel:#0e1e31;--panel2:#12283e;--line:#29435d;--muted:#92a9bf;--text:#edf5ff;--cyan:#53d5e8;--amber:#f6bd60;--red:#ff657a;--green:#52d6a0}}
body{{font:18px Inter,Segoe UI,Arial,sans-serif;color:var(--text);background:linear-gradient(140deg,#0b1a2b,#07111f 65%)}}
.appbar{{height:76px;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 34px;gap:20px;background:#091726}}
.logo{{font-size:23px;font-weight:800;letter-spacing:1.5px}}.logo b{{color:var(--cyan)}}.env{{border:1px solid #8d6d36;background:#382d1b;color:#ffd58b;padding:8px 13px;border-radius:6px;font-size:13px;font-weight:800;letter-spacing:1.2px}}
.right{{margin-left:auto;display:flex;align-items:center;gap:18px;color:var(--muted);font-size:15px}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--amber);margin-right:7px}}
.layout{{display:flex;height:920px}}aside{{width:245px;background:#091625;border-right:1px solid var(--line);padding:24px 14px}}
.navtitle{{color:#68849e;font-size:12px;letter-spacing:2px;font-weight:800;margin:6px 13px 18px}}
.navitem{{height:48px;display:flex;align-items:center;gap:13px;padding:0 12px;border-radius:7px;color:#9db2c7;font-size:15px;margin-bottom:5px}}
.navitem.active{{color:#eafaff;background:#15334a;border:1px solid #27556a}}.navnum{{font-size:12px;color:var(--cyan);font-weight:800}}
.aside-note{{margin:30px 7px 0;padding:14px;border:1px solid #34465a;border-radius:8px;color:#9db2c7;font-size:12px;line-height:1.6}}
main{{flex:1;padding:27px 31px;overflow:hidden}}
.crumb{{font-size:13px;color:#8ca7c0;letter-spacing:1.5px;font-weight:700}}
.heading{{display:flex;align-items:flex-start;justify-content:space-between;margin:12px 0 19px}}
h1{{font-size:34px;margin:0 0 8px;letter-spacing:-.6px}}.subtitle{{font-size:15px;color:#9db2c7}}
.badge{{border:1px solid #6b5938;color:#ffd58b;background:#2b251b;padding:10px 13px;border-radius:6px;font-size:12px;letter-spacing:1px;font-weight:800}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin-bottom:15px}}
.kpi{{background:linear-gradient(135deg,#12283e,#0e1e31);border:1px solid var(--line);border-radius:10px;padding:15px 18px;height:100px}}
.klabel{{font-size:12px;color:#8ca7c0;letter-spacing:1px;text-transform:uppercase}}.kvalue{{font-size:27px;font-weight:800;margin-top:9px}}.kfoot{{font-size:11px;color:var(--muted);margin-top:3px}}
.contentgrid{{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:14px}}
.panel{{background:linear-gradient(135deg,#10243a,#0c1b2c);border:1px solid var(--line);border-radius:10px;padding:17px 19px;min-height:250px}}
.panelhead{{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}}h2{{font-size:17px;margin:0;font-weight:750}}.panelmeta{{font-size:11px;color:#8ca7c0;letter-spacing:1px}}
.chip{{display:inline-block;border:1px solid #35536e;color:#b9d4e9;border-radius:5px;padding:5px 8px;font-size:11px;font-weight:700}}
.red{{color:var(--red)}}.amber{{color:var(--amber)}}.green{{color:var(--green)}}.cyan{{color:var(--cyan)}}
.chart{{width:100%;height:125px;display:block}}.legend{{display:flex;gap:18px;color:#a3b8ca;font-size:11px;margin-top:4px}}.key{{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:5px}}
.eventrow{{display:grid;grid-template-columns:72px 11px 1fr;gap:9px;align-items:start;margin:13px 0;font-size:13px;color:#c6d6e5}}
.eventtime{{font-family:Consolas,monospace;color:#8ba7c1;font-size:12px}}.eventdot{{height:9px;width:9px;border-radius:50%;background:var(--cyan);margin-top:4px;box-shadow:0 0 0 4px #18374b}}
.eventrow.critical .eventdot{{background:var(--red);box-shadow:0 0 0 4px #452534}}.eventrow.warning .eventdot{{background:var(--amber);box-shadow:0 0 0 4px #40351f}}
.smallmuted{{color:#91a8bd;font-size:12px;line-height:1.55}}
.bottomgrid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}
.table{{width:100%;border-collapse:collapse;font-size:12px}}.table td,.table th{{padding:9px 7px;border-bottom:1px solid #263d54;text-align:left}}.table th{{color:#8ca7c0;font-size:10px;letter-spacing:1px}}
.progress{{height:5px;background:#20364b;border-radius:4px;overflow:hidden;margin-top:13px}}.progress>span{{display:block;height:100%;width:{progress}%;background:linear-gradient(90deg,#38b6d2,#67e1c0)}}
.foot{{height:84px;border-top:1px solid var(--line);display:flex;align-items:center;padding:0 31px;gap:24px;background:#081522;color:#91a8bd;font-size:12px}}
.foot strong{{color:#d9e9f8}}.foot .grow{{flex:1}}.timeline{{display:flex;align-items:center;gap:0;margin:17px 0 12px}}.step{{flex:1;text-align:center;position:relative;color:#829bb1;font-size:10px}}.step:before{{content:"";display:block;width:13px;height:13px;border-radius:50%;background:#28465e;border:2px solid #53718b;margin:0 auto 7px;position:relative;z-index:2}}.step:after{{content:"";position:absolute;height:2px;left:50%;right:-50%;top:6px;background:#28465e;z-index:1}}.step:last-child:after{{display:none}}.step.done:before{{background:var(--green);border-color:var(--green)}}.step.current:before{{background:var(--amber);border-color:var(--amber);box-shadow:0 0 0 5px #3a3020}}
.visualsvg{{width:100%;height:100%;display:block}}.node{{fill:#142f46;stroke:#3b6a89;stroke-width:1.5}}.nodehot{{fill:#38242e;stroke:#d35c70;stroke-width:1.5}}.nodetext{{fill:#e8f4ff;font-size:15px;font-weight:700}}.nodesub{{fill:#9bb5cb;font-size:11px}}.edge{{stroke:#47718c;stroke-width:2;fill:none}}.edgedash{{stroke:#e5ad4d;stroke-width:2;stroke-dasharray:6 5;fill:none}}
</style></head><body>
<header class="appbar"><div class="logo"><b>◈</b> AIOPS <span style="color:#819bb3;font-weight:400">/ DEMO CENTER</span></div>
<div class="env">SIMULATION · READ ONLY</div><div class="right"><span><i class="dot"></i>Runtime live : non connecté</span><span>Build visuel · v2.13.x</span></div></header>
<div class="layout"><aside><div class="navtitle">OPÉRATIONS</div>{nav}
<div class="aside-note"><strong style="color:#f4c878">MODE DE PREUVE</strong><br>Scénario reproductible hors ligne.<br>Snapshots générés par navigateur.<br><span style="color:#ffcf7c">Pas de capture runtime réelle.</span></div></aside>
<main><div class="crumb">OPÉRATIONS / PARCOURS INCIDENT / ÉTAPE {number}</div>
<div class="heading"><div><h1>{escape(title)}</h1><div class="subtitle">{escape(narration)}</div></div><div class="badge">{escape(status)}</div></div>
<div class="kpis">
<div class="kpi"><div class="klabel">Incident</div><div class="kvalue red">INC-SAN-042</div><div class="kfoot">ID synthétique · priorité P1</div></div>
<div class="kpi"><div class="klabel">Services impactés</div><div class="kvalue">03</div><div class="kfoot">Payments · Core Banking · Batch</div></div>
<div class="kpi"><div class="klabel">Événements corrélés</div><div class="kvalue cyan">12</div><div class="kfoot">Fenêtre fictive de 90 secondes</div></div>
<div class="kpi"><div class="klabel">État de la remédiation</div><div class="kvalue amber">BLOQUÉE</div><div class="kfoot">Aucune commande live autorisée</div></div>
</div>
<div class="contentgrid">
<section class="panel"><div class="panelhead"><h2>{escape(phase)} · Vue opérationnelle</h2><span class="chip">SNAPSHOT {index+1:02d}/09</span></div>{visual}</section>
<section class="panel"><div class="panelhead"><h2>Chronologie de l'incident</h2><span class="panelmeta">TEMPS SIMULÉ</span></div>
<div class="eventrow critical"><span class="eventtime">10:42:01</span><span class="eventdot"></span><div><strong class="red">Perte de synchronisation SAN</strong><div class="smallmuted">brocade-fc01 · événement source simulé</div></div></div>
<div class="eventrow warning"><span class="eventtime">10:42:08</span><span class="eventdot"></span><div><strong class="amber">Chemins multipath dégradés</strong><div class="smallmuted">hôte esx-prod-07 · signal corrélé fictif</div></div></div>
<div class="eventrow"><span class="eventtime">10:42:14</span><span class="eventdot"></span><div><strong>Analyse et contrôle de politique</strong><div class="smallmuted">Hypothèse évaluée ; preuve runtime absente</div></div></div>
<div class="eventrow"><span class="eventtime">10:42:31</span><span class="eventdot"></span><div><strong>Validation humaine attendue</strong><div class="smallmuted">Pas de ticket GLPI ni d'approbation réelle</div></div></div>
<div class="smallmuted" style="border-top:1px solid #29435d;padding-top:10px;margin-top:8px">Les horodatages, ressources et événements sont des données de scénario, pas des logs collectés.</div></section>
</div>
<div class="bottomgrid">
<section class="panel" style="min-height:158px"><div class="panelhead"><h2>Pipeline de décision</h2><span class="panelmeta">PARCOURS STAR</span></div>
<div class="timeline"><div class="step done">Detect</div><div class="step done">Correlate</div><div class="step done">Analyse IA</div><div class="step current">Policy / HITL</div><div class="step">Remediate</div><div class="step">Verify</div></div>
<div class="smallmuted">Étape mise en évidence : {escape(phase)}. Les étapes non exécutées ne sont pas présentées comme accomplies.</div></section>
<section class="panel" style="min-height:158px"><div class="panelhead"><h2>Provenance & garde-fous</h2><span class="chip amber">SYNTHÉTIQUE</span></div>
<table class="table"><tr><td>Origine des données</td><td><strong class="amber">SIMULATED_TARGET</strong></td></tr><tr><td>Runtime authentifié</td><td class="red">NON</td></tr><tr><td>Attestation DGX indépendante</td><td class="red">NON</td></tr><tr><td>Action live autorisée</td><td class="green">NON — verrouillée</td></tr></table>
</section></div><div class="progress"><span></span></div></main></div>
<footer class="foot"><span><strong>AIOPS / STAR</strong> · {escape(phase)}</span><span class="grow">{escape(disclaimer)}</span><span>SCÈNE {index+1:02d} / {total:02d}</span><span>{progress}%</span></footer>
</body></html>"""


def _scene_visual(index: int) -> str:
    """Return a distinct, self-contained visual for each step of the synthetic scenario."""
    if index == 0:
        return """<svg class="chart" viewBox="0 0 700 180" role="img" aria-label="Courbe synthétique de latence SAN">
<g stroke="#233c53" stroke-width="1"><path d="M40 25H680M40 60H680M40 95H680M40 130H680M40 165H680"/></g>
<path d="M40 130 L90 126 L140 131 L190 120 L240 127 L290 123 L340 125 L390 40 L440 31 L490 51 L540 24 L590 35 L640 18 L680 25 L680 165 L40 165Z" fill="#ff657a" opacity=".12"/>
<path d="M40 130 L90 126 L140 131 L190 120 L240 127 L290 123 L340 125 L390 40 L440 31 L490 51 L540 24 L590 35 L640 18 L680 25" fill="none" stroke="#ff657a" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M40 148 L90 149 L140 146 L190 150 L240 148 L290 147 L340 149 L390 143 L440 145 L490 142 L540 144 L590 141 L640 143 L680 142" fill="none" stroke="#53d5e8" stroke-width="3"/>
<text x="42" y="14" fill="#9bb5cb" font-size="11">LATENCE / PERTE DE CHEMIN — VALEURS ILLUSTRATIVES</text><text x="515" y="174" fill="#9bb5cb" font-size="10">T+00 → T+90 s</text></svg>
<div class="legend"><span><i class="key" style="background:#ff657a"></i>Latence SAN (synthétique)</span><span><i class="key" style="background:#53d5e8"></i>Chemins actifs (synthétique)</span></div>"""
    if index == 1:
        return """<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
<div style="padding:14px;background:#132b40;border:1px solid #36566f;border-radius:8px"><div class="panelmeta">SOURCE A</div><strong style="display:block;margin:10px 0" class="red">SAN / FC</strong><div class="smallmuted">fabric: brocade-fc01<br>port: 1/24<br>signal: sync-loss</div></div>
<div style="padding:14px;background:#132b40;border:1px solid #36566f;border-radius:8px"><div class="panelmeta">SOURCE B</div><strong style="display:block;margin:10px 0" class="amber">HÔTE / MULTIPATH</strong><div class="smallmuted">esx-prod-07<br>paths: 8 → 2<br>signal: degraded</div></div>
<div style="grid-column:1/3;text-align:center;color:#53d5e8;font-size:13px;padding:7px">↓ fenêtre de corrélation · Δt ≤ 90 s ↓</div>
<div style="grid-column:1/3;padding:16px;border:1px solid #b95469;background:#34212d;border-radius:8px"><strong class="red">INC-SAN-042 · P1</strong><div class="smallmuted">Association proposée : perte de synchro et dégradation multipath. Confiance et lien causal non validés par le runtime.</div></div></div>"""
    if index == 2:
        return """<svg class="visualsvg" viewBox="0 0 700 225" role="img" aria-label="Topologie de dépendances illustratives">
<path class="edge" d="M350 55V85M350 110L180 145M350 110L520 145M180 175V195M520 175V195"/>
<rect class="nodehot" x="240" y="10" rx="8" width="220" height="46"/><text class="nodetext" x="350" y="29" text-anchor="middle">Fabric SAN</text><text class="nodesub" x="350" y="44" text-anchor="middle">brocade-fc01 · simulé</text>
<rect class="node" x="240" y="85" rx="8" width="220" height="42"/><text class="nodetext" x="350" y="103" text-anchor="middle">Cluster virtualisation</text><text class="nodesub" x="350" y="118" text-anchor="middle">esx-prod-07 · hypothèse</text>
<rect class="node" x="55" y="145" rx="8" width="250" height="42"/><text class="nodetext" x="180" y="163" text-anchor="middle">Payments</text><text class="nodesub" x="180" y="178" text-anchor="middle">service critique · dépendance fictive</text>
<rect class="node" x="395" y="145" rx="8" width="250" height="42"/><text class="nodetext" x="520" y="163" text-anchor="middle">Core Banking</text><text class="nodesub" x="520" y="178" text-anchor="middle">service métier · dépendance fictive</text>
<text x="350" y="218" text-anchor="middle" fill="#f6bd60" font-size="12">TOPOLOGIE DE DÉMONSTRATION — NON EXTRAITE D'UNE CMDB LIVE</text></svg>"""
    if index == 3:
        return """<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
<div style="border:1px solid #31516a;border-radius:8px;padding:14px"><span class="chip">HYPOTHÈSE A</span><h2 style="margin:14px 0 8px;color:#f6bd60">Perte de lien FC</h2><div class="smallmuted">Éléments compatibles : sync-loss, baisse des chemins actifs, hausse de latence.</div><div class="progress"><span style="width:72%;background:#f6bd60"></span></div><div class="smallmuted">Score illustratif : 0,72 — non calculé par un modèle live</div></div>
<div style="border:1px solid #31516a;border-radius:8px;padding:14px"><span class="chip">HYPOTHÈSE B</span><h2 style="margin:14px 0 8px;color:#53d5e8">Défaut côté hôte</h2><div class="smallmuted">À vérifier : pilote HBA, erreurs d'interface, état des chemins et changements récents.</div><div class="progress"><span style="width:38%;background:#53d5e8"></span></div><div class="smallmuted">Score illustratif : 0,38 — non calculé par un modèle live</div></div>
<div style="grid-column:1/3;padding:12px;border-left:3px solid #f6bd60;background:#192a39"><strong>Critique indépendante</strong><div class="smallmuted">Ne pas remédier sur le seul score. Collecter les compteurs HBA, l'état des ports et les changements récents ; conserver l'action bloquée jusqu'à validation.</div></div></div>"""
    if index == 4:
        return """<div class="panelmeta" style="margin-bottom:12px">FICHE INCIDENT · APERÇU SYNTHÉTIQUE</div>
<div style="border:1px solid #38536a;border-radius:8px;overflow:hidden">
<div style="padding:12px;background:#162c41;display:flex;justify-content:space-between"><strong>INC-SAN-042</strong><span class="chip" style="color:#ff8292;border-color:#a94b60">P1 · MAJEUR</span></div>
<div style="padding:12px 14px"><div class="smallmuted">TITRE</div><strong>Dégradation du fabric SAN — synchronisation perdue</strong></div>
<div style="padding:12px 14px;border-top:1px solid #2a435a"><div class="smallmuted">IMPACT PROPOSÉ</div><strong>Payments / Core Banking — à confirmer</strong></div>
<div style="padding:12px 14px;border-top:1px solid #2a435a"><div class="smallmuted">ÉLÉMENTS JOINTS</div><span class="chip">12 événements fictifs</span> <span class="chip">Topologie illustrative</span> <span class="chip">Plan de contrôle</span></div>
<div style="padding:12px 14px;border-top:1px solid #2a435a"><div class="smallmuted">ÉTAT D'INTÉGRATION</div><strong class="amber">APERÇU UNIQUEMENT — AUCUN TICKET CRÉÉ</strong></div></div>"""
    if index == 5:
        return """<div style="border:1px solid #8d6d36;background:#2d271d;border-radius:9px;padding:15px;margin-bottom:12px"><div class="panelmeta" style="color:#ffd58b">POINT DE CONTRÔLE</div><h2 style="font-size:21px;margin:10px 0">Approbation explicite requise</h2><div class="smallmuted" style="color:#e4d3b2">Toute modification du fabric ou du multipath est interdite sans preuve live, fenêtre de changement et approbation humaine enregistrée.</div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
<div style="padding:16px;border:1px solid #37536b;border-radius:8px"><strong class="green">Conditions requises</strong><div class="smallmuted" style="margin-top:10px">✓ Plan d'action borné<br>✓ Pré-contrôles définis<br>✓ Rollback documenté</div></div>
<div style="padding:16px;border:1px solid #8d4658;border-radius:8px;background:#291c28"><strong class="red">Conditions manquantes</strong><div class="smallmuted" style="margin-top:10px">✕ Attestation runtime<br>✕ Approbation authentifiée<br>✕ Fenêtre de changement</div></div></div>
<div style="margin-top:13px;padding:12px;text-align:center;background:#40252d;border:1px solid #9c4d5c;border-radius:7px;color:#ff9cab;font-weight:800;letter-spacing:1px">DÉCISION : DENY / HOLD — AUCUNE ACTION</div>"""
    if index == 6:
        return """<div class="panelmeta">PLAN DRY-RUN · AUCUNE COMMANDE EXÉCUTÉE</div>
<div style="margin-top:12px">
<div class="eventrow"><span class="eventtime">STEP 01</span><span class="eventdot"></span><div><strong>Collecter l'état des ports</strong><div class="smallmuted">Lecture seule — non exécutée</div></div></div>
<div class="eventrow"><span class="eventtime">STEP 02</span><span class="eventdot"></span><div><strong>Comparer les chemins multipath</strong><div class="smallmuted">Précondition : snapshot runtime signé</div></div></div>
<div class="eventrow warning"><span class="eventtime">STEP 03</span><span class="eventdot"></span><div><strong>Isoler la cause avant toute action</strong><div class="smallmuted">Pas de reset port, zoning ou failover automatique</div></div></div>
<div class="eventrow critical"><span class="eventtime">STEP 04</span><span class="eventdot"></span><div><strong>Exécution bloquée par policy</strong><div class="smallmuted">Aucun shell, API d'équipement ou ordonnanceur appelé</div></div></div>
</div>"""
    if index == 7:
        return """<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
<div style="padding:15px;border:1px solid #914859;border-radius:8px"><div class="panelmeta">AVANT · ILLUSTRATIF</div><div style="font-size:29px;font-weight:800;color:#ff657a;margin:12px 0">2 / 8</div><div class="smallmuted">Chemins actifs</div><div class="progress"><span style="width:25%;background:#ff657a"></span></div><div style="font-size:20px;font-weight:700;margin-top:15px;color:#ff657a">184 ms</div><div class="smallmuted">Latence illustrative</div></div>
<div style="padding:15px;border:1px solid #3d8a73;border-radius:8px"><div class="panelmeta">APRÈS · CIBLE, NON MESURÉE</div><div style="font-size:29px;font-weight:800;color:#52d6a0;margin:12px 0">8 / 8</div><div class="smallmuted">Objectif de chemins</div><div class="progress"><span style="width:100%"></span></div><div style="font-size:20px;font-weight:700;margin-top:15px;color:#52d6a0">&lt; 10 ms</div><div class="smallmuted">Objectif de latence</div></div>
<div style="grid-column:1/3;padding:12px;border:1px dashed #8d6d36;border-radius:7px;color:#ffd58b;font-size:12px">ATTENTION : les valeurs « après » sont des objectifs de démonstration, pas des mesures post-remédiation.</div></div>"""
    return """<div class="panelmeta" style="margin-bottom:12px">DOSSIER DE PREUVES · INVENTAIRE DE QUALIFICATION</div>
<table class="table"><thead><tr><th>ÉLÉMENT</th><th>STATUT</th><th>PROVENANCE</th></tr></thead><tbody>
<tr><td>Snapshots des 9 scènes</td><td class="green">GÉNÉRÉS</td><td>Rendu Chromium local</td></tr>
<tr><td>Chronologie d'incident</td><td class="amber">SIMULÉE</td><td>Fixture de scénario</td></tr>
<tr><td>Logs du runtime Debian</td><td class="red">ABSENTS</td><td>Non collectés</td></tr>
<tr><td>Réponse DGX indépendante</td><td class="red">ABSENTE</td><td>Non attestée</td></tr>
<tr><td>GLPI / n8n / Grafana live</td><td class="red">NON QUALIFIÉS</td><td>Pas de connexion</td></tr>
</tbody></table><div style="margin-top:14px;padding:11px;background:#182a3a;border-left:3px solid #53d5e8" class="smallmuted">Critère de sortie : remplacer chaque fixture par une capture authentifiée, horodatée et hachée avant toute revendication live.</div>"""

def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def generate(output: Path, scenario: str = "SAN_FABRIC_P1", voice: bool = True) -> dict:
    ffmpeg = require_command("ffmpeg")
    ffprobe = require_command("ffprobe")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright Python absent. Installez-le puis installez Chromium.") from exc

    scenes = scenes_for(scenario)
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError("Le répertoire de sortie ne doit pas être un lien symbolique.")
    video = output / "AIOps-Demo-Complete.mp4"
    subtitles = output / "AIOps-Demo-Complete.srt"
    report_path = output / "AIOps-Demo-Complete.manifest.json"
    snapshots = output / "snapshots"
    architecture_path = output / "AIOps-Architecture-Illustrative.svg"
    for path in (video, subtitles, report_path, snapshots, architecture_path):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refus d'écraser un fichier existant : {path}")
    snapshots.mkdir()
    with tempfile.TemporaryDirectory(prefix="aiops-demo-video-") as tmp:
        root = Path(tmp)
        frames = snapshots
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            for index, scene in enumerate(scenes):
                page.set_content(scene_html(scene, index, len(scenes)), wait_until="load")
                page.screenshot(path=str(frames / f"scene-{index+1:02d}.png"), full_page=True, animations="disabled")
            browser.close()

        concat = root / "video.ffconcat"
        lines = ["ffconcat version 1.0"]
        for index in range(len(scenes)):
            lines += [f"file '{(frames / f'scene-{index+1:02d}.png').as_posix()}'", f"duration {DURATION}"]
        lines.append(f"file '{(frames / f'scene-{len(scenes):02d}.png').as_posix()}'")
        concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

        srt_lines = []
        for i, scene in enumerate(scenes):
            start, end = i * DURATION, (i + 1) * DURATION
            def stamp(seconds: int) -> str:
                return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d},000"
            srt_lines.extend([str(i+1), f"{stamp(start)} --> {stamp(end)}", scene[2], scene[6], ""])
        subtitles.write_text("\ufeff" + "\n".join(srt_lines), encoding="utf-8")

        audio_args: list[str] = []
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        narration_status = "disabled"
        audio_file = root / "narration.wav"
        if voice and espeak:
            wavs = []
            for i, scene in enumerate(scenes):
                raw_wav = root / f"voice-raw-{i:02d}.wav"
                wav = root / f"voice-{i:02d}.wav"
                run([espeak, "-v", "fr", "-s", "145", "-w", str(raw_wav), scene[2] + " " + scene[6]])
                # Keep every narration segment aligned to its 8-second scene.
                run([ffmpeg, "-y", "-i", str(raw_wav), "-af", f"apad=pad_dur={DURATION},atrim=duration={DURATION}",
                     "-ac", "2", "-ar", "44100", str(wav)])
                wavs.append(wav)
            audio_concat = root / "audio.ffconcat"
            audio_concat.write_text("ffconcat version 1.0\n" + "".join(f"file '{p.as_posix()}'\n" for p in wavs), encoding="utf-8")
            run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat), "-ac", "2", "-ar", "44100", str(audio_file)])
            audio_args = ["-i", str(audio_file)]
            narration_status = "espeak_french_scene_aligned"
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), *audio_args,
             "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
             "-crf", "21", *(["-c:a", "aac", "-shortest"] if audio_args else ["-an"]),
             "-movflags", "+faststart", str(video)])

    # Do not publish a manifest for an empty, truncated, or malformed video.
    if not video.is_file() or video.stat().st_size == 0:
        raise RuntimeError("Rendu MP4 absent ou vide.")
    if not subtitles.is_file() or subtitles.stat().st_size == 0:
        raise RuntimeError("Sous-titres absents ou vides.")
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
         "-of", "json", str(video)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    media = json.loads(probe.stdout)
    duration = float(media.get("format", {}).get("duration", 0))
    streams = media.get("streams", [])
    if not (len(scenes) * DURATION - 1 <= duration <= len(scenes) * DURATION + 1):
        raise RuntimeError(f"Durée MP4 inattendue : {duration:.3f}s.")
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video_stream or video_stream.get("width") != WIDTH or video_stream.get("height") != HEIGHT:
        raise RuntimeError("Le MP4 ne contient pas le flux vidéo HD attendu.")
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    if narration_status == "espeak_french_scene_aligned" and not has_audio:
        raise RuntimeError("Narration annoncée mais aucune piste audio n'est présente.")
    if not has_audio and narration_status != "disabled":
        raise RuntimeError("État de narration incohérent avec le média produit.")

    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    snapshot_hashes = {p.name: sha256_file(p) for p in sorted(snapshots.glob("scene-*.png"))}
    if len(snapshot_hashes) != len(scenes):
        raise RuntimeError("Le nombre de snapshots navigateur ne correspond pas au storyboard.")
    architecture_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="650" viewBox="0 0 1800 650">
<rect width="1800" height="650" rx="24" fill="#07111f"/><text x="70" y="70" fill="#edf5ff" font-family="Arial" font-size="34" font-weight="700">AIOps — chaîne de décision (illustration)</text>
<text x="70" y="110" fill="#f6bd60" font-family="Arial" font-size="18">SCÉNARIO SYNTHÉTIQUE · AUCUN BACKEND LIVE INTERROGÉ</text>
<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#53d5e8"/></marker></defs>
<g stroke="#53d5e8" stroke-width="3" fill="none" marker-end="url(#arrow)"><path d="M260 250 H340"/><path d="M540 250 H620"/><path d="M820 250 H900"/><path d="M1100 250 H1180"/><path d="M1380 250 H1460"/></g>
<g font-family="Arial" text-anchor="middle"><rect x="60" y="190" width="200" height="120" rx="12" fill="#142f46" stroke="#3b6a89" stroke-width="2"/><text x="160" y="232" fill="#edf5ff" font-size="22" font-weight="700">Télémétrie</text><text x="160" y="266" fill="#9bb5cb" font-size="16">Prometheus / Grafana</text>
<rect x="340" y="190" width="200" height="120" rx="12" fill="#142f46" stroke="#3b6a89" stroke-width="2"/><text x="440" y="232" fill="#edf5ff" font-size="22" font-weight="700">Corrélation</text><text x="440" y="266" fill="#9bb5cb" font-size="16">n8n / événement</text>
<rect x="620" y="190" width="200" height="120" rx="12" fill="#142f46" stroke="#3b6a89" stroke-width="2"/><text x="720" y="232" fill="#edf5ff" font-size="22" font-weight="700">Contexte</text><text x="720" y="266" fill="#9bb5cb" font-size="16">CMDB / RAG</text>
<rect x="900" y="190" width="200" height="120" rx="12" fill="#142f46" stroke="#3b6a89" stroke-width="2"/><text x="1000" y="232" fill="#edf5ff" font-size="22" font-weight="700">Analyse IA</text><text x="1000" y="266" fill="#9bb5cb" font-size="16">Analyste + critique</text>
<rect x="1180" y="190" width="200" height="120" rx="12" fill="#382d1b" stroke="#f6bd60" stroke-width="2"/><text x="1280" y="232" fill="#ffd58b" font-size="22" font-weight="700">Policy / HITL</text><text x="1280" y="266" fill="#e4d3b2" font-size="16">GLPI · validation</text>
<rect x="1460" y="190" width="260" height="120" rx="12" fill="#142f46" stroke="#3b6a89" stroke-width="2"/><text x="1590" y="232" fill="#edf5ff" font-size="22" font-weight="700">Action contrôlée</text><text x="1590" y="266" fill="#9bb5cb" font-size="16">Dry-run → verify / rollback</text>
<path d="M1590 310 V390 H1000 V310" stroke="#f6bd60" stroke-width="2" stroke-dasharray="8 7" fill="none" marker-end="url(#arrow)"/><text x="1290" y="425" fill="#f6bd60" font-size="17">Vérification / rollback — chemin conceptuel</text>
<rect x="70" y="490" width="1650" height="90" rx="12" fill="#291c28" stroke="#9c4d5c" stroke-width="2"/><text x="100" y="528" fill="#ff9cab" font-size="20" font-family="Arial" font-weight="700">Garde-fous transverses</text><text x="100" y="558" fill="#f4dce1" font-size="17" font-family="Arial">Fencing · provenance des preuves · deny-by-default · approbation humaine · aucune action live dans cette démo</text></g></svg>"""
    architecture_path.write_text(architecture_svg + "\n", encoding="utf-8")
    manifest = {
        "schema": "aiops-demo-video-manifest-v2",
        "snapshots_directory": "snapshots",
        "snapshot_count": len(snapshot_hashes),
        "snapshot_sha256": snapshot_hashes,
        "architecture_illustration": architecture_path.name,
        "architecture_sha256": sha256_file(architecture_path),
        "scenario": scenario,
        "provenance": "SIMULATED_TARGET",
        "scene_count": len(scenes),
        "duration_target_seconds": len(scenes) * DURATION,
        "duration_actual_seconds": round(duration, 3),
        "resolution": f"{WIDTH}x{HEIGHT}",
        "video": video.name,
        "video_size_bytes": video.stat().st_size,
        "video_sha256": sha256_file(video),
        "subtitles": subtitles.name,
        "subtitles_sha256": sha256_file(subtitles),
        "audio_track_present": has_audio,
        "narration": narration_status,
        "runtime_authenticated": False,
        "dgx_independently_attested": False,
        "live_execution_qualified": False,
        "live_action_authorized": False,
        "notice": "Browser-rendered illustrative UI snapshots; no runtime endpoint or production action was used.",
    }
    report_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a complete synthetic AIOps demo video")
    parser.add_argument("--out", type=Path, default=Path("dist/aiops-demo-video"))
    parser.add_argument("--scenario", choices=("SAN_FABRIC_P1", "PAYMENTS_P2"), default="SAN_FABRIC_P1")
    parser.add_argument("--no-voice", action="store_true", help="Create video and subtitles without optional French TTS")
    args = parser.parse_args()
    manifest = generate(args.out, args.scenario, not args.no_voice)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
