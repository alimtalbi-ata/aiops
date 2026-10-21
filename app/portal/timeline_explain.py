"""Read-only timeline explainers. All events come from Core; prose is explanatory."""
from html import escape
from urllib.parse import quote

STAGES = {
 "INGEST": ("Réception de l'incident", "Core enregistre la création du run.", "Déclenchement initial depuis une source d'incident."),
 "NORMALIZE": ("Normalisation", "Le workflow normalise les données disponibles.", "Préparer un incident cohérent pour les étapes suivantes."),
 "CORRELATE": ("Corrélation", "Le workflow rapproche les événements disponibles.", "Rechercher les liens possibles sans présumer la causalité."),
 "CMDB": ("Contexte CMDB", "Le workflow exploite le contexte CI et services.", "Identifier les dépendances concernées."),
 "OBSERVE": ("Observabilité", "Le workflow collecte les observations configurées.", "Établir des preuves horodatées avec provenance."),
 "RAG": ("Documentation", "Le workflow prépare le contexte documentaire.", "Ajouter des informations sans les confondre avec des mesures."),
 "DGX_ANALYST": ("Analyse IA", "L'Analyst propose une classification et des hypothèses.", "Expliquer le diagnostic et ses limites à partir des preuves."),
 "DGX_CRITIC": ("Contre-expertise IA", "Le Critic examine les affirmations et risques de l'analyse.", "Contester les conclusions non étayées."),
 "POLICY": ("Gouvernance Policy", "Le moteur de règles examine une décision.", "Autoriser ou refuser selon les garde-fous."),
 "RUN": ("Orchestration", "Core enregistre une transition d'état.", "Suivre la progression ou l'arrêt du run."),
}

def safe(x):
    return escape(str(x if x is not None else "INCONNU")[:700])

def event_facts(e):
    """Render only bounded, recorded Core event data; never invent AI rationale."""
    payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
    refs = e.get("evidence_ids") if isinstance(e.get("evidence_ids"), list) else []
    parts = []
    if refs:
        parts.append("<p><strong>Preuves liées :</strong> " +
                     ", ".join(safe(x) for x in refs[:30]) + "</p>")
    if e.get("confidence") is not None:
        parts.append("<p><strong>Confiance enregistrée :</strong> " +
                     safe(e["confidence"]) + " (non calibrée)</p>")
    analysis = payload.get("analysis")
    if isinstance(analysis, dict):
        parts.append("<p><strong>Résultat Analyst :</strong> sévérité " +
                     safe(analysis.get("severity")) + ", confiance " +
                     safe(analysis.get("confidence")) + "</p>")
        hypotheses = analysis.get("hypotheses")
        if isinstance(hypotheses, list):
            for h in hypotheses[:5]:
                if isinstance(h, dict):
                    parts.append("<p><strong>Hypothèse :</strong> " +
                                 safe(h.get("statement")) + " · preuves " +
                                 ", ".join(safe(x) for x in h.get("supporting_evidence_ids", [])[:10]) +
                                 "</p>")
    critique = payload.get("critique")
    if isinstance(critique, dict):
        parts.append("<p><strong>Résultat Critic :</strong> validé=" +
                     safe(critique.get("validated")) + " · recommandation " +
                     safe(critique.get("final_recommendation")) + "</p>")
        issues = critique.get("issues")
        if isinstance(issues, list):
            for issue in issues[:12]:
                if isinstance(issue, dict):
                    parts.append("<p><strong>Objection " + safe(issue.get("code")) +
                                 " :</strong> " + safe(issue.get("description")) + "</p>")
    for field in ("reason", "error", "failure_reason", "message"):
        if isinstance(payload.get(field), (str, int, float)):
            parts.append("<p><strong>" + safe(field) + " :</strong> " +
                         safe(payload[field]) + "</p>")
    # Other fields remain accessible as a bounded, escaped inspectable record.
    import json
    if payload:
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        parts.append("<details><summary>Entrées/sorties enregistrées (JSON Core)</summary><pre>" +
                     escape(serialized[:12000]) + "</pre></details>")
    return "".join(parts) or "<p>Aucune donnée détaillée enregistrée pour cet événement.</p>"


def event_box(e, n):
    if not isinstance(e, dict):
        return ""
    stage = str(e.get("stage") or "INCONNU")
    event = str(e.get("event_type") or "INCONNU")
    status = str(e.get("status") or "INCONNU")
    title, activity, objective = STAGES.get(stage, ("Événement enregistré", "Une étape a produit un événement.", "Lire les données enregistrées."))
    explanation = "Événement réellement enregistré par Core."
    if event == "STAGE_STARTED":
        explanation = "Démarrée par la progression du workflow ; le résultat n'est pas encore connu."
    if event == "CRITIC_COMPLETED" and status == "BLOCKED":
        explanation = "Le Critic n'a pas validé la poursuite automatique. Voir ses objections dans le panneau ci-dessous."
    if event == "STATE_TRANSITION" and status == "BLOCKED":
        explanation = "Le run a été arrêté ; les événements précédents et les registres déterminent pourquoi."
    return ('<article class="event"><h3>Box #' + str(n) + ' · ' + safe(title) + '</h3>'
            '<p><strong>Étape technique :</strong> ' + safe(stage) + '</p>'
            '<p><strong>Quand :</strong> ' + safe(e.get("occurred_at")) + '</p>'
            '<p><strong>Événement :</strong> ' + safe(event) + ' · <strong>État :</strong> ' + safe(status)
            + ' · <strong>Décision :</strong> ' + safe(e.get("decision")) + '</p>'
            '<p><strong>Que fait la plateforme :</strong> ' + safe(activity) + '</p>'
            '<p><strong>Pourquoi :</strong> ' + safe(objective) + '</p>'
            '<p><strong>Ce qui s’est passé :</strong> ' + safe(explanation) + '</p>'
            + event_facts(e)
            + '<small>Source : événement Core persistant ; explication fonctionnelle, pas raisonnement interne caché du modèle.</small></article>')

def run_selector(runs, selected):
    links = []
    for x in runs[:60]:
        if not isinstance(x, dict):
            continue
        rid = str(x.get("run_id", ""))
        if not rid or len(rid) > 128 or not all(c.isalnum() or c in "-_" for c in rid):
            continue
        current = ' aria-current="page"' if rid == selected else ""
        links.append('<li><a href="/timeline?run_id=' + quote(rid, safe="") + '"' + current + '>'
                     + safe(rid) + ' · ' + safe(x.get("status")) + ' · ' + safe(x.get("mode")) + '</a></li>')
    return '<ul>' + ''.join(links) + '</ul>' if links else '<p>Aucun run accessible.</p>'


def incident_explorer(runs, selected, query="", status_filter="ALL", incidents=None):
    """Group persisted runs by Core incident; display unexecuted incidents honestly."""
    from collections import defaultdict
    grouped = defaultdict(list)
    for run in runs:
        if isinstance(run, dict) and run.get("incident_id"):
            grouped[str(run["incident_id"])].append(run)
    catalog = {}
    for record in (incidents or []):
        if isinstance(record, dict) and record.get("incident_id"):
            catalog[str(record["incident_id"])] = record
    for incident in grouped:
        catalog.setdefault(incident, {"incident_id": incident})
    output = ['<form method="get" action="/timeline"><label>Rechercher un incident ou run '
              '<input name="q" value="' + safe(query) + '" placeholder="INC-… / RUN-…"></label> '
              '<label>État <select name="status">']
    for value in ("ALL", "RUNNING", "CREATED", "RESOLVED", "BLOCKED", "FAILED", "CANCELLED", "NO_RUN"):
        output.append('<option value="' + value + '"' + (' selected' if value == status_filter else '') +
                      '>' + value + '</option>')
    output.append('</select></label> <button type="submit">Filtrer</button></form>')
    q = query.casefold()
    shown = 0
    for incident, meta in catalog.items():
        siblings = grouped.get(incident, [])
        matching = [x for x in siblings if
                    (status_filter == "ALL" or x.get("status") == status_filter) and
                    (not q or q in incident.casefold() or q in str(x.get("run_id", "")).casefold())]
        empty = not siblings and status_filter in ("ALL", "NO_RUN")
        matches_query = not q or q in incident.casefold() or q in str(meta.get("title", "")).casefold()
        if not matching and not (empty and matches_query):
            continue
        shown += 1
        output.append('<details' + (' open' if any(x.get("run_id") == selected for x in siblings) else '') +
                      '><summary><strong>' + safe(incident) + '</strong> — ' +
                      safe(meta.get("title") or "Titre non disponible") + ' · ' +
                      safe(meta.get("severity") or "Sévérité inconnue") +
                      ' · ' + str(len(siblings)) + ' run(s)</summary>')
        if matching:
            output.append(run_selector(matching, selected))
        else:
            output.append('<p>Aucun run enregistré pour cet incident.</p>')
        output.append('</details>')
    if not shown:
        output.append('<p>Aucun incident correspondant aux filtres.</p>')
    return ''.join(output)
