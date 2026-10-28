"""Read-only, source-backed Demo Studio V2 investigation view."""
from datetime import datetime, timezone
import re
from urllib.parse import quote
from portal.ui_theme import panel, table, esc


def _source(value):
    """Report transport authentication separately from unverified source content.

    An HTTP 401/403 label requires an actual captured HTTPError, never a
    user-controlled JSON field claiming an HTTP status or a generic exception.
    """
    if not isinstance(value, dict) or not value:
        return "INCONNU — réponse absente ou invalide"
    if value.get("status") == "UNKNOWN" or "error_type" in value:
        if value.get("error_type") == "HTTPError":
            code = value.get("http_status")
            if type(code) is int and code == 401:
                return "ACCÈS REFUSÉ — HTTP 401 (authentification Core requise)"
            if type(code) is int and code == 403:
                return "ACCÈS REFUSÉ — HTTP 403 (droits Core insuffisants)"
        return "INCONNU — source non vérifiée ou indisponible"
    return "DISPONIBLE — données reçues (non attestées)"


def _run_navigation(run):
    """Only Core-safe IDs may become links; never interpolate untrusted HTML."""
    rid = run.get("run_id")
    if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", rid):
        return panel("Navigation du run", "<p>INCONNU — identifiant Core absent ou invalide ; lien indisponible.</p>")
    url = "/timeline?run_id=" + quote(rid, safe="")
    return panel("Navigation du run",
        '<p><a href="' + url + '">Ouvrir la timeline Core de ce run</a> · '
        '<a href="/runs">Tous les runs Core</a></p>'
        '<p>Lecture seule. La timeline affiche les événements enregistrés, sans prouver un effet LIVE.</p>')


def _event_clock(events, clock):
    """Most recent valid Core event timestamp, not a heartbeat or live attestation."""
    valid = []
    invalid = False
    for event in events:
        if not isinstance(event, dict):
            invalid = True
            continue
        raw = event.get("occurred_at")
        try:
            if not isinstance(raw, str):
                raise ValueError("missing timestamp")
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed > clock:
                raise ValueError("unverifiable timestamp")
            valid.append(parsed)
        except (ValueError, OverflowError, TypeError):
            invalid = True
    if invalid:
        return None, "INCONNU — horodatage Core manquant, futur ou invalide"
    if not valid:
        return None, "INCONNU — aucun événement horodaté"
    last = max(valid)
    return last, last.astimezone(timezone.utc).isoformat()



def _ordered_events(events):
    """Render Core sequence order, but never certify incomplete chronology.

    Core assigns positive per-run sequence numbers. A gap, duplicate or
    impossible clock prevents both a canonical-order claim and stale inference.
    """
    if events is None:
        return [], "INCONNU — événements Core indisponibles", False
    if not events:
        return [], "INCONNU — aucun événement Core ; fraîcheur non vérifiable", False
    if any(not isinstance(e, dict) or type(e.get("sequence")) is not int
           or e["sequence"] < 1 for e in events):
        return events, "INCONNU — séquence Core absente ou invalide ; ordre non vérifié", False
    ordered = sorted(events, key=lambda e: e["sequence"])
    sequences = [e["sequence"] for e in ordered]
    if len(set(sequences)) != len(sequences):
        return events, "INCONNU — séquences Core dupliquées ; ordre non vérifié", False
    if sequences[0] != 1:
        return ordered, "INCONNU — chronologie Core sans première séquence ; événements potentiellement manquants", False
    if any(b != a + 1 for a, b in zip(sequences, sequences[1:])):
        return ordered, "INCONNU — lacune de séquence Core ; événements potentiellement manquants", False
    clocks = []
    for e in ordered:
        raw = e.get("occurred_at")
        try:
            if not isinstance(raw, str):
                raise ValueError("timestamp missing")
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("timezone missing")
        except (ValueError, OverflowError, TypeError):
            return ordered, "INCONNU — horodatages Core incomplets ou invalides", False
        clocks.append(stamp)
    if any(b < a for a, b in zip(clocks, clocks[1:])):
        return ordered, "INCONNU — horodatages Core non monotones", False
    return ordered, "COHÉRENT — ordre par séquence Core (non attesté indépendamment)", True


def render_demo_v2(detail, ledger, gates, now=None):
    """No fabricated evidence, impact, remediation or LLM decisions."""
    detail = detail if isinstance(detail, dict) else {}
    run = detail.get("run") if isinstance(detail.get("run"), dict) else detail
    events = detail.get("events")
    if not isinstance(events, list):
        events = None
    status = str(run.get("status") or "INCONNU")
    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    started = run.get("started_at") or run.get("created_at")
    age_label = "INCONNU"
    start_clock = None
    if isinstance(started, str):
        try:
            dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                age = (clock - dt).total_seconds()
                if age < 0:
                    age_label = "INCONNU — horodatage Core futur"
                else:
                    start_clock = dt
                if age >= 86400:
                    age_label = f"Ancien ({int(age // 86400)} jours) — état à requalifier"
                elif age >= 3600:
                    age_label = f"{int(age // 3600)} h depuis le début"
                elif age >= 0:
                    age_label = "Démarré récemment (heure Core)"
        except ValueError:
            pass
    ordered_events, sequence_label, sequence_ok = _ordered_events(events)
    synthetic = False
    evidence_ids = set()
    rows = []
    for e in ordered_events:
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
    last_event, last_event_label = _event_clock(events, clock) if events is not None else (None, "INCONNU — événements Core indisponibles")
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
            ("Dernier événement Core (UTC)", last_event_label),
            ("Intégrité de la chronologie", sequence_label),
            ("Événements Core", len(events) if events is not None else "INCONNU"),
            ("Identifiants de preuves référencés", len(evidence_ids) if events is not None else "INCONNU"),
            ("Observations synthétiques", "OUI — au moins un événement" if synthetic else "NON CONFIRMÉ"),
            ("Registre Analyst/Critic", _source(ledger)),
            ("Décisions Policy", _source(gates)),
        ]))
    # A stale RUNNING warning needs a verifiable timestamp. Missing/malformed
    # events must not be interpreted as proof that no progress occurred.
    # An old start timestamp without a complete event timeline cannot prove inactivity.
    last_activity = last_event if events and sequence_ok else None
    if (status == "RUNNING" and start_clock is not None
            and last_activity is not None
            and (clock - last_activity).total_seconds() >= 1800):
        body += panel("Attention — statut RUNNING ancien à requalifier",
            "<p>Plus de 30 minutes depuis le dernier horodatage Core vérifiable. "
            "Cela ne prouve ni un blocage, ni une absence d'activité LIVE.</p>")
    elif status == "RUNNING" and (events is None or not sequence_ok or last_event is None):
        body += panel("Fraîcheur RUNNING — INCONNU",
            "<p>Les séquences ou horodatages Core ne permettent pas de qualifier "
            "la fraîcheur. Aucune activité LIVE n'est attestée.</p>")
    body += _run_navigation(run)
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
