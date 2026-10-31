"""Read-only, source-backed Demo Studio V2 investigation view."""
from datetime import datetime, timezone
from portal.ui_theme import panel, table, esc


def _source(value):
    if not isinstance(value, dict):
        return "INCONNU — réponse absente"
    if value.get("status") == "UNKNOWN":
        error = str(value.get("error_type", ""))
        if error in ("HTTPError", "Unauthorized", "401"):
            return "INDISPONIBLE — accès ou API en erreur (vérifier les droits)"
        return "INDISPONIBLE — source non accessible"
    return "DISPONIBLE — données reçues"


def render_stage_marker_warning(detail):
    """Show a visible warning only for actual DEMO stage markers from Core."""
    if not isinstance(detail, dict):
        return ""
    run = detail.get("run") if isinstance(detail.get("run"), dict) else detail
    events = detail.get("events")
    if run.get("mode") not in ("DEMO", "REPLAY", "STORY") or not isinstance(events, list):
        return ""
    if not any(isinstance(e, dict) and e.get("event_type") == "STAGE_COMPLETED"
               and e.get("stage") in ("POLICY", "HITL", "REMEDIATE", "VERIFY")
               for e in events):
        return ""
    return panel("Étapes DEMO — validation non attestée",
        "<p>Les événements STAGE_COMPLETED/PASS affichés ci-dessous "
        "sont des marqueurs de workflow synthétiques. Ils ne prouvent "
        "ni approbation humaine GLPI, ni remédiation effectuée, ni "
        "mesure de vérification. Un marqueur POLICY ne prouve pas "
        "une décision Policy PASS/SIMULATE : consulter la gate "
        "et les liens Analysis/Critique/Evidence correspondants. "
        "RESOLVED n'atteste aucune action LIVE.</p>")


def render_demo_v2(detail, ledger, gates):
    """No fabricated evidence, impact, remediation or LLM decisions."""
    detail = detail if isinstance(detail, dict) else {}
    run = detail.get("run") if isinstance(detail.get("run"), dict) else detail
    events = detail.get("events")
    if not isinstance(events, list):
        events = None
    status = str(run.get("status") or "INCONNU")
    started = run.get("started_at") or run.get("created_at")
    age_label = "INCONNU"
    if isinstance(started, str):
        try:
            dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                age = (datetime.now(timezone.utc) - dt).total_seconds()
                if age >= 86400:
                    age_label = f"Ancien ({int(age // 86400)} jours) — état à requalifier"
                elif age >= 3600:
                    age_label = f"{int(age // 3600)} h depuis le début"
                else:
                    age_label = "Démarré récemment (heure Core)"
        except ValueError:
            pass
    synthetic = False
    evidence_ids = set()
    rows = []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        synthetic = synthetic or payload.get("synthetic") is True
        for eid in e.get("evidence_ids", []) if isinstance(e.get("evidence_ids"), list) else []:
            if isinstance(eid, str):
                evidence_ids.add(eid)
        rows.append((
            e.get("sequence", "INCONNU"),
            e.get("occurred_at", "INCONNU"),
            e.get("stage", "INCONNU"),
            e.get("event_type", "INCONNU"),
            e.get("status", "INCONNU"),
            e.get("decision") or "—",
        ))
    gate_items = gates.get("items") if isinstance(gates, dict) else None
    decisions = []
    if isinstance(gate_items, list):
        for g in gate_items:
            if isinstance(g, dict):
                decisions.append((
                    g.get("stage", "INCONNU"),
                    g.get("state", "INCONNU"),
                    g.get("decision") or "INCONNU",
                    g.get("reason") or "Motif non fourni",
                ))
    body = panel("Mission Control V2 — provenance et fraîcheur",
        '<p>Lecture seule · événements historiques enregistrés dans Core. '
        'Un statut RESOLVED ne prouve pas une remédiation en production.</p>' +
        table(["Contrôle", "Valeur"], [
            ("Run", run.get("run_id", "INCONNU")),
            ("Mode", run.get("mode", "INCONNU")),
            ("État Core", status),
            ("Fraîcheur du run", age_label),
            ("Événements Core", len(events) if events is not None else "INCONNU"),
            ("Identifiants de preuves référencés", len(evidence_ids) if events is not None else "INCONNU"),
            ("Observations synthétiques", "OUI — au moins un événement" if synthetic else "NON CONFIRMÉ"),
            ("Registre Analyst/Critic", _source(ledger)),
            ("Décisions Policy", _source(gates)),
        ]))
    body += render_stage_marker_warning(detail)
    if status == "RUNNING" and age_label.startswith("Ancien"):
        body += panel("Attention — exécution potentiellement bloquée",
            "<p>Core indique RUNNING, mais le démarrage est ancien. "
            "Aucune progression récente n'est démontrée par cette seule donnée.</p>")
    body += panel("Chronologie canonique — Core",
        table(["#", "Date UTC", "Étape", "Événement", "État", "Décision"], rows)
        if events is not None else "<p>INCONNU — événements Core indisponibles.</p>")
    body += panel("Policy — décisions et justification",
        table(["Étape", "Gate", "Décision", "Motif"], decisions)
        if isinstance(gate_items, list) else
        "<p>INCONNU — décisions Policy indisponibles.</p>")
    body += panel("Périmètre des preuves",
        "<p>Les identifiants sont des références Core, pas une validation indépendante "
        "du contenu Evidence. Les événements marqués synthetic sont des simulations. "
        "Aucune dépendance métier SAN n'est inférée sans réponse d'impact Twin.</p>"
        + (table(["Identifiant Core"], [(eid,) for eid in sorted(evidence_ids)])
           if evidence_ids else "<p>Aucun identifiant de preuve confirmé.</p>"))
    return body
