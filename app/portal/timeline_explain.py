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
            '<small>Source : événement Core persistant ; explication fonctionnelle, pas raisonnement interne caché du modèle.</small></article>')

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


def incident_explorer(runs, selected, query="", status_filter="ALL"):
    """Group the existing Core run registry by incident_id; never invent incidents."""
    from collections import defaultdict
    grouped = defaultdict(list)
    for run in runs:
        if isinstance(run, dict) and run.get("incident_id"):
            grouped[str(run["incident_id"])].append(run)
    output = ['<form method="get" action="/timeline"><label>Rechercher un incident ou run '
              '<input name="q" value="' + safe(query) + '" placeholder="INC-… / RUN-…"></label> '
              '<label>État <select name="status">']
    for value in ("ALL", "RUNNING", "CREATED", "RESOLVED", "BLOCKED", "FAILED", "CANCELLED"):
        output.append('<option value="' + value + '"' + (' selected' if value == status_filter else '') +
                      '>' + value + '</option>')
    output.append('</select></label> <button type="submit">Filtrer</button></form>')
    q = query.casefold()
    shown = 0
    for incident, siblings in grouped.items():
        matching = [x for x in siblings if
                    (status_filter == "ALL" or x.get("status") == status_filter) and
                    (not q or q in incident.casefold() or q in str(x.get("run_id", "")).casefold())]
        if not matching:
            continue
        shown += 1
        output.append('<details' + (' open' if any(x.get("run_id") == selected for x in siblings) else '') +
                      '><summary><strong>' + safe(incident) + '</strong> · ' +
                      str(len(siblings)) + ' run(s), ' + str(len(matching)) +
                      ' affiché(s)</summary>' + run_selector(matching, selected) + '</details>')
    if not shown:
        output.append('<p>Aucun run correspondant aux filtres.</p>')
    return ''.join(output)
