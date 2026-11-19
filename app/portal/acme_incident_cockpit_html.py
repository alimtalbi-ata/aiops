"""Script-free operator presentation for the unified synthetic incident cockpit."""
from __future__ import annotations

from html import escape
from portal.acme_workbench_presentation import render_story_context, render_runtime_refusals

from portal.acme_evidence_collection_plan import EVIDENCE_REQUIREMENTS


def render_synthetic_cockpit_html(cockpit: dict) -> str:
    if (not isinstance(cockpit, dict)
            or cockpit.get("schema") != "aiops.synthetic-incident-cockpit.v1"
            or cockpit.get("mode") != "DEMO"
            or cockpit.get("overall_qualification") != "UNKNOWN"
            or cockpit.get("runtime_attested") is not False
            or cockpit.get("live_remediation_authorized") is not False):
        raise ValueError("unqualified_cockpit_html")
    lifecycle = cockpit["lifecycle"]
    readiness = cockpit["itil_readiness"]
    evidence = cockpit["evidence_plan"]
    review = cockpit["analyst_critic_review"]
    if (len(lifecycle["stages"]) != 9 or len(readiness["transitions"]) != 8
            or evidence["requested_count"] != 9 or evidence["verified_count"] != 0
            or review["policy_disposition"] != "DENY_LIVE_ACTION"
            or review["critic_disposition"] != "HOLD_FOR_HUMAN_REVIEW"
            or review.get("human_approval_verified") is not False
            or review.get("independent_postcheck_verified") is not False
            or review.get("operational_decision_authorized") is not False
            or readiness.get("authorized_transition_count") != 0
            or readiness.get("next_operator_step") != "COLLECT_INDEPENDENT_RUNTIME_EVIDENCE_READ_ONLY"
            or any(stage["evidence_state"] != "UNKNOWN" for stage in lifecycle["stages"])
            or any(t["authorized"] is not False for t in readiness["transitions"])
            or any(r["evidence_state"] != "MISSING" for r in evidence["requests"])):
        raise ValueError("unqualified_cockpit_details")
    def safe(value: object) -> str:
        return escape(str(value), quote=True)
    stage_rows = "".join(
        "<tr><th scope='row'>" + safe(s["phase"]) + "</th><td>"
        + safe(s["expected_source"]) + "</td><td>" + safe(s["evidence_state"])
        + "</td></tr>" for s in lifecycle["stages"]
    )
    customer_explanations = {
        "detect": ("Signal SAN candidat", "Vérifier la règle et l'alerte Grafana en lecture seule"),
        "correlate": ("Regrouper les signaux en incident P1", "Vérifier la corrélation NOC"),
        "enrich": ("Relier le SAN au service Payments", "Contrôler les dépendances métier/CMDB"),
        "analyze": ("Formuler puis contester une hypothèse", "Exiger des citations Analyst/Critic indépendantes"),
        "ticket": ("Préparer la traçabilité ITIL", "Lire le ticket GLPI et son ACL sans écriture"),
        "approve": ("Soumettre la décision à Policy/HITL", "Obtenir une approbation humaine authentifiée"),
        "simulate": ("Montrer une simulation sans effet", "Conserver le reçu isolé sans action LIVE"),
        "verify": ("Exiger une vérification indépendante", "Comparer des mesures post-incident authentifiées"),
        "close": ("Préparer Problem et PIR", "Ne pas clôturer sans preuve ni autorisation"),
    }
    if [s["cue"] for s in lifecycle["stages"]] != list(customer_explanations):
        raise ValueError("unexpected_demo_timeline")
    timeline_rows = "".join(
        "<tr><th scope='row'>" + safe(index) + ". " + safe(customer_explanations[s["cue"]][0])
        + "</th><td>" + safe(s["expected_source"])
        + "</td><td>UNKNOWN — preuve runtime absente</td><td>"
        + safe(customer_explanations[s["cue"]][1]) + "</td></tr>"
        for index, s in enumerate(lifecycle["stages"], start=1)
    )
    # Evidence requirements are read from the validated projection, never
    # invented receipts. Display required metadata without accepting uploads.
    if ([request.get("checkpoint") for request in evidence["requests"]]
            != [stage["cue"] for stage in lifecycle["stages"]]
            or any(request.get("collection_mode") != "MANUAL_READ_ONLY_INDEPENDENT_REVIEW"
                   or request.get("submitted_evidence") is not None
                   or request.get("attested") is not False
                   or request.get("qualifies_runtime") is not False
                   or request.get("required_metadata")
                   != ["observed_at", "source_id", "content_sha256"]
                   or request.get("required_evidence_type")
                   != EVIDENCE_REQUIREMENTS[request["checkpoint"]][0]
                   or request.get("expected_source")
                   != lifecycle["stages"][index]["expected_source"]
                   for index, request in enumerate(evidence["requests"]))
            or evidence.get("evidence_acceptance_enabled") is not False
            or evidence.get("outbound_collection_enabled") is not False):
        raise ValueError("unqualified_evidence_requirements")
    evidence_rows = "".join(
        "<tr><th scope='row'>" + safe(index) + ". " + safe(request["checkpoint"])
        + "</th><td>" + safe(request["required_evidence_type"])
        + "</td><td>" + safe(request["expected_source"])
        + "</td><td>observed_at, source_id, content_sha256</td>"
        "<td>MISSING — contrôle humain requis</td></tr>"
        for index, request in enumerate(evidence["requests"], start=1)
    )
    transition_rows = "".join(
        "<tr><th scope='row'>" + safe(t["transition"]) + "</th><td>"
        + safe(", ".join(t["missing_evidence"])) + "</td><td>NON</td></tr>"
        for t in readiness["transitions"]
    )
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>AIOPS2 — Cockpit incident DEMO</title>"
        "<link rel='stylesheet' href='/assets/aiops-theme.css'>"
        "<style>body{font:16px system-ui,sans-serif;max-width:1150px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}table{border-collapse:collapse;width:100%;"
        "margin:1rem 0 2rem}th,td{border:1px solid #777;padding:.6rem;text-align:left}"
        "thead{background:#eee;color:#111}.warning{border-left:5px solid #9a6700;"
        "padding:1rem;background:#fff7dd;color:#302400}"
        "code{overflow-wrap:anywhere}html{scroll-behavior:smooth}"
        "h2[id],div[id]{scroll-margin-top:1rem}"
        "nav{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;"
        "margin:1rem 0;padding:.75rem;background:#f2f5fa;border-radius:.5rem}"
        ".portal-cross-nav{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;"
        "margin:.8rem 0;padding:.65rem;background:#111827;border:1px solid #293650;border-radius:12px}"
        ".portal-cross-nav a{display:inline-flex;align-items:center;min-height:36px;"
        "padding:.4rem .7rem;border:1px solid #3a4a6b;border-radius:8px;"
        "background:#172136;color:#60a5fa;text-decoration:none;font-weight:600}"
        ".portal-cross-nav a:hover{border-color:#8b5cf6;color:#a78bfa}"
        "nav a{display:inline-block;padding:.35rem .65rem;border:1px solid #44546a;"
        "border-radius:.35rem;color:#153a63;background:#fff}"
        "a:focus-visible{outline:3px solid #125da0;outline-offset:3px}"
        ".demo-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));"
        "gap:.7rem;margin:1rem 0}.demo-card{padding:.8rem;border:1px solid #536273;"
        "border-radius:.5rem}.demo-card strong{display:block;font-size:1.1rem}"
        ".demo-card p{margin:.25rem 0;font-size:.9rem}"
        ".table-scroll{overflow-x:auto;max-width:100%;margin-bottom:1rem}"
        ".table-scroll table{min-width:650px}"
        "dt{margin-top:.8rem}dd{margin-left:1rem}"
        "@media(max-width:700px){body{margin:1rem auto}.demo-cards{grid-template-columns:1fr}.portal-cross-nav a{flex:1 1 42%;justify-content:center}"
        "nav{align-items:stretch}nav a{flex:1 1 40%;text-align:center}}"
        "@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}"
        "body{background:#080b14;color:#f4f7ff}a{color:#38bdf8}thead{background:#172136;color:#f4f7ff}nav{background:#111827}nav a{background:#172136;color:#38bdf8;border-color:#64748b}.demo-card{background:#111827}.warning{background:#31251b;color:#fff0cc;border-color:#fbbf24}a:focus-visible,summary:focus-visible{outline:3px solid #38bdf8;outline-offset:3px}details{background:#111827;padding:1rem;border-radius:12px;margin:1rem 0}summary{cursor:pointer;font-weight:bold}.table-scroll:focus-visible{outline:3px solid #38bdf8;outline-offset:3px}td,th{overflow-wrap:normal;word-break:normal}.story-context{background:#111827;padding:1rem;border-radius:12px}.story-context dl{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:.35rem .8rem}.story-context dt,.story-context dd{margin:0;min-width:0}.story-context dd{overflow-wrap:anywhere;font-family:ui-monospace,monospace}@media(max-width:700px){.story-context dl{grid-template-columns:1fr}.story-context dt{font-weight:600}.story-context dd{margin-bottom:.35rem}}.scroll-hint{font-size:.875rem;color:#b8c7df}@media(max-width:700px){h1{font-size:1.55rem;margin:.5rem 0}.warning{padding:.65rem}.demo-cards{gap:.35rem;margin:.65rem 0}.demo-card{padding:.55rem}.demo-card strong{font-size:1rem}.demo-card p{font-size:.85rem;margin:.1rem 0}nav{padding:.5rem}} </style></head><body><main>"
        "<a class='portal-skip-link' href='#impact'>Aller au parcours SAN vers Payments</a>"
        "<header><a href='/'>AIOPS2 Portal</a><nav class='portal-cross-nav' aria-label='Navigation espace opérateur'>"
        "<a href='/#noc'>Cockpit NOC</a><a href='/demo/explore-story'>Explore / Story</a>"
        "<a href='/demo/acme-impact'>Digital Twin</a><a href='/#incidents'>Incidents</a>"
        "<a href='/#runs'>Runs</a><a href='#workbench'>Workbench</a></nav></header>"
        "<h1>AIOPS2 — Cockpit incident → ITIL</h1>"
        "<p class='warning'><strong>DEMO SYNTHÉTIQUE — NO-GO LIVE.</strong> "
        "Aucune preuve runtime authentifiée, aucun ticket GLPI modifié, "
        "aucune exécution Temporal ni remédiation autorisée.</p>"
        "<div class='demo-cards' aria-label='Résumé de qualification'>"
        "<div class='demo-card'><strong>GO — scénario synthétique</strong>"
        "<p>Corrélation SAN vers Payments sur fixture locale.</p></div>"
        "<div class='demo-card'><strong>UNKNOWN — preuves runtime</strong>"
        "<p>Aucune source réelle ni récupération indépendante attestée.</p></div>"
        "<div class='demo-card'><strong>NO-GO LIVE</strong>"
        "<p>Aucune action réelle ni clôture GLPI autorisée.</p></div></div>"
        "<nav aria-label='Parcours guidé de démonstration'>"
        "<strong>Démo guidée (8–12 min) :</strong> "
        "<a href='#impact'>1. Impact métier</a> · "
        "<a href='#workbench'>2. Preuves</a> · "
        "<a href='#decision'>3. Décision</a> · "
        "<a href='#itil'>4. ITIL</a> · "
        "<a href='#verdict'>5. Verdict</a></nav>"
        "<h2>Parcours démontrable — SAN vers Payments</h2>"
        "<p>Signal SAN → incident P1 → impact Payments → hypothèses Analyst/Critic "
        "→ décision Policy/HITL → simulation isolée → vérification indépendante "
        "→ préparation ITIL.</p>"
        "<p><strong>Ce qui est démontré :</strong> corrélation des identifiants "
        "et empreinte de la même fixture synthétique; neuf étapes et huit "
        "transitions inspectables. <strong>Ce qui reste inconnu :</strong> "
        "preuve runtime, effet réel, récupération indépendante et autorisation "
        "de clôture.</p>"
        "<p>Contrat de démonstrabilité : <code>"
        "python scripts/verify_aiops2_demo_acceptance.py</code> "
        "(rapport JSON hors ligne; pas une attestation de production).</p>"
        "<p><a href='/demo/acme-grafana-pilot-preview'>Voir l'observation Grafana synthétique non attestée</a> — "
        "UNKNOWN / BLOCKED, sans accès réseau ni qualification runtime.</p>"
        "<h2 id='impact'>Incident et impact métier</h2><p>SAN P1 : <code>"
        + safe(cockpit["incident_id"]) + "</code> · Payments P2 : <code>"
        + safe(cockpit["business_impact_incident_id"]) + "</code></p>"
        "<p>Chemin d'impact : " + safe(" → ".join(cockpit["business_impact_path"]))
        + "</p><details class='secondary-detail'><summary>Chronologie explicative — 9 étapes UNKNOWN, pas événements observés</summary>"
        "<p>Neuf étapes attendues, aucune horodatée ni attestée. "
        "La prochaine vérification ne constitue pas une action exécutée.</p>"
        "<p class='scroll-hint'>Tableau : défilement horizontal si nécessaire, avec les flèches après Tab.</p><div class='table-scroll' role='region' aria-label='Chronologie métier' tabindex='0'><table><thead><tr><th>Étape métier</th><th>Source attendue</th>"
        "<th>État de preuve</th><th>Prochaine vérification</th></tr></thead>"
        "<tbody>" + timeline_rows + "</tbody></table></div></details>"
        "<details class='secondary-detail'><summary>Cycle incident — 9 étapes UNKNOWN</summary><p class='scroll-hint'>Tableau : défilement horizontal si nécessaire, avec les flèches après Tab.</p><div class='table-scroll' role='region' aria-label='Cycle incident' tabindex='0'><table><thead><tr>"
        "<th>Étape</th><th>Source attendue</th><th>Preuve</th></tr></thead>"
        "<tbody>" + stage_rows + "</tbody></table></div></details>"
        " <span id='evidence' aria-hidden='true'></span><h2 id='workbench'>Evidence Workbench — lecture seule</h2>"
        "<p><strong>0 / 9 preuves vérifiées · 9 MISSING · NO-GO LIVE</strong></p>"
        "<p>Fixture synthétique hors ligne. Liaison tenant, Run Core et attempt non attestée : UNKNOWN. Aucun lien implicite vers un Run réel.</p>"
        + render_story_context(cockpit) + render_runtime_refusals() +
        "<details><summary>Registre des preuves attendues — 9 MISSING</summary>"
        "<p>Chaque ligne est une demande de preuve, pas une pièce collectée. "
        "Les champs observed_at, source_id et content_sha256 doivent être "
        "contrôlés indépendamment avant toute qualification. "
        "Aucun dépôt, appel sortant ou validation automatique ici.</p>"
        "<div class='table-scroll' role='region' aria-label='Registre des preuves attendues' tabindex='0'><table><thead><tr><th>Point de contrôle</th><th>Preuve exigée</th>"
        "<th>Source attendue</th><th>Métadonnées requises</th>"
        "<th>État</th></tr></thead><tbody>" + evidence_rows + "</tbody></table></div></details>"
        "<section aria-label='Fiche de décision opérationnelle'>"
        "<h2>Fiche de décision — que peut faire le NOC ?</h2>"
        "<dl><dt><strong>Ce que nous savons</strong></dt><dd>"
        "Le scénario synthétique relie le P1 SAN au P2 Payments par une "
        "fixture locale cohérente ; il ne prouve pas un incident réel.</dd>"
        "<dt><strong>Ce qui manque</strong></dt><dd>"
        "Neuf preuves indépendantes sur neuf ; lectures Grafana, NOC, GLPI "
        "et postcheck authentifiées non disponibles.</dd>"
        "<dt><strong>Qui doit valider</strong></dt><dd>"
        "Un opérateur NOC habilité et un approbateur HITL authentifié ; "
        "aucune approbation n'est vérifiée.</dd>"
        "<dt><strong>Pourquoi c'est bloqué</strong></dt><dd>"
        "Critic : HOLD_FOR_HUMAN_REVIEW ; Policy : DENY_LIVE_ACTION ; "
        "postcheck indépendant UNKNOWN ; huit transitions ITIL refusées.</dd>"
        "<dt><strong>Prochaine étape permise</strong></dt><dd>"
        "Collecter et examiner les preuves en lecture seule, puis demander "
        "une vérification indépendante. Pas d'exécution Temporal, de "
        "remédiation LIVE ni de clôture GLPI.</dd></dl></section>"
        "<h2 id='decision'>Analyst / Critic / Policy</h2><p>Analyst : hypothèse déterministe, "
        "pas une conclusion LLM vérifiée. Critic : "
        + safe(review["critic_disposition"]) + ". Policy : "
        + safe(review["policy_disposition"]) + ".</p>"
        "<p>Preuves indépendantes vérifiées : <strong>0 / "
        + safe(evidence["requested_count"]) + "</strong>. "
        "Prochaine action : collecte manuelle en lecture seule, "
        "puis vérification indépendante.</p>"
        "<h2 id='itil'>Transitions ITIL (8)</h2><details><summary>8 transitions non autorisées — preuves manquantes</summary><p class='scroll-hint'>Tableau : défilement horizontal si nécessaire, avec les flèches après Tab.</p><div class='table-scroll' role='region' aria-label='Transitions ITIL' tabindex='0'><table><thead><tr>"
        "<th>Transition</th><th>Preuves manquantes</th><th>Autorisée</th>"
        "</tr></thead><tbody>" + transition_rows + "</tbody></table></div></details>"
        "<div id='verdict' class='warning'><strong>Décision opérateur :</strong> "
        "GO pour le scénario synthétique ; UNKNOWN pour les preuves runtime ; "
        "NO-GO LIVE pour toute action réelle ou clôture GLPI.</div>"
        "<p>SHA-256 de la fixture : <code>" + safe(cockpit["source_sha256"])
        + "</code></p></main></body></html>"
    )
