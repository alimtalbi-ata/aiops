"""Human-readable, repeatable AIOps2 report section for GLPI tickets."""
import html
import json


_START = '<section id="aiops2-ai-report">'
_END = '</section>'


def _object(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


def _text(value, fallback="Non renseigné"):
    if value is None or value == "":
        return fallback
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return str(value)


def _items(value):
    return value if isinstance(value, list) else []


def _list_section(title, values):
    values = [x for x in _items(values) if x not in (None, "", [], {})]
    if not values:
        return f"<h3>{html.escape(title)}</h3><p>Non renseigné.</p>"
    return f"<h3>{html.escape(title)}</h3><ul>" + "".join(
        f"<li>{html.escape(_text(item))}</li>" for item in values
    ) + "</ul>"


def render_run_report(detail, ledger=None, *, sync_stage="UPDATE"):
    """Render the latest Core snapshot; no invented facts or inferred resolution."""
    ledger = ledger if isinstance(ledger, dict) else {}
    run = detail.get("run") if isinstance(detail, dict) else {}
    run = run if isinstance(run, dict) else {}
    events = [e for e in _items(detail.get("events")) if isinstance(e, dict)]
    events.sort(key=lambda e: (e.get("sequence", 0), e.get("occurred_at", "")))
    esc = lambda value: html.escape(_text(value))
    out = [
        _START,
        "<h2>Compte rendu AIOps2 — mise à jour automatique</h2>",
        "<p><strong>Run :</strong> " + esc(run.get("run_id")) +
        " &nbsp; <strong>Incident :</strong> " + esc(run.get("incident_id")) + "</p>",
        "<p><strong>Scénario :</strong> " + esc(run.get("scenario_id")) +
        " &nbsp; <strong>Mode :</strong> " + esc(run.get("mode")) +
        " &nbsp; <strong>État Core :</strong> " + esc(run.get("status")) + "</p>",
        "<p><strong>Étape de synchronisation :</strong> " + esc(sync_stage) +
        " &nbsp; <strong>Confiance globale :</strong> " +
        esc(run.get("overall_confidence")) + "</p>",
        "<h3>Chronologie</h3>",
    ]
    if events:
        out.append("<ol>")
        for event in events:
            label = " — ".join(str(x) for x in (
                event.get("occurred_at"), event.get("stage"),
                event.get("event_type"), event.get("status")
            ) if x)
            details = []
            if event.get("decision"):
                details.append("Décision : " + str(event["decision"]))
            if event.get("confidence") is not None:
                details.append("Confiance : " + str(event["confidence"]))
            if event.get("evidence_ids"):
                details.append("Preuves : " + ", ".join(map(str, event["evidence_ids"])))
            out.append("<li><strong>" + html.escape(label) + "</strong>" +
                       ("<br>" + html.escape(" | ".join(details)) if details else "") +
                       "</li>")
        out.append("</ol>")
    else:
        out.append("<p>Aucun événement disponible.</p>")

    analyses = _items(ledger.get("analyses"))
    critiques = _items(ledger.get("critiques"))
    policies = _items(ledger.get("policy_decisions"))
    analysis = {}
    for item in analyses:
        if isinstance(item, dict) and item.get("status") == "VALID":
            analysis = _object(item.get("output"))
    critique = {}
    for item in critiques:
        if isinstance(item, dict):
            critique = _object(item.get("output"))
    if not analysis:
        for event in reversed(events):
            analysis = _object(_object(event.get("payload")).get("analysis"))
            if analysis:
                break
    if not critique:
        for event in reversed(events):
            critique = _object(_object(event.get("payload")).get("critique"))
            if critique:
                break

    out.append("<h3>Analyse IA</h3>")
    if analysis:
        for key, label in (
            ("summary", "Synthèse"), ("severity", "Sévérité"),
            ("confidence", "Confiance"), ("diagnosis", "Diagnostic"),
            ("root_cause", "Cause racine proposée"),
        ):
            if analysis.get(key) not in (None, "", [], {}):
                out.append("<p><strong>" + label + " :</strong> " +
                           esc(analysis[key]) + "</p>")
        out.append(_list_section("Faits observés", analysis.get("facts")))
        out.append(_list_section("Hypothèses", analysis.get("hypotheses")))
        out.append(_list_section("Actions recommandées", analysis.get("recommended_actions")))
        out.append(_list_section("Incertitudes et limites", analysis.get("uncertainties") or analysis.get("limitations")))
    else:
        out.append("<p>Analyse structurée indisponible dans le ledger.</p>")

    out.append("<h3>Contrôle Critic</h3>")
    if critique:
        out.append("<p><strong>Validation :</strong> " +
                   esc(critique.get("validated")) + "</p>")
        out.append(_list_section("Objections", critique.get("issues")))
        out.append(_list_section("Actions jugées dangereuses", critique.get("unsafe_actions")))
        out.append(_list_section("Éléments manquants", critique.get("missing_evidence")))
    else:
        out.append("<p>Critique indisponible.</p>")

    hitl_events = [
        event for event in events
        if event.get("event_type") == "HITL_PROPOSAL_CREATED"
        and isinstance(event.get("payload"), dict)
    ]
    out.append("<h3>Proposition HITL</h3>")
    if hitl_events:
        out.append("<ul>")
        for event in hitl_events:
            payload = event["payload"]
            out.append("<li><strong>Proposition :</strong> " +
                       esc(payload.get("proposal_id")) +
                       "<br><strong>Empreinte :</strong> " +
                       esc(payload.get("proposal_hash")) +
                       "<br><strong>Statut :</strong> " +
                       esc(payload.get("proposal_status")) +
                       "<br><strong>Exécution :</strong> NON AUTORISÉE</li>")
        out.append("</ul>")
    else:
        out.append("<p>Aucune proposition HITL créée pour ce Run.</p>")

    out.append("<h3>Décisions Policy</h3>")
    if policies:
        out.append("<ul>")
        for policy in policies:
            if isinstance(policy, dict):
                out.append("<li>" + esc({
                    "decision_id": policy.get("policy_decision_id"),
                    "decision": policy.get("decision"),
                    "state": policy.get("state"),
                    "reason": policy.get("reason"),
                }) + "</li>")
        out.append("</ul>")
    else:
        out.append("<p>Aucune décision Policy structurée disponible.</p>")

    evidence = sorted({
        str(eid)
        for event in events for eid in _items(event.get("evidence_ids"))
        if eid
    })
    out.append(_list_section("Références de preuves", evidence))
    final_status = run.get("status")
    if final_status == "RESOLVED":
        closing = "Run déclaré RESOLVED par Core. En DEMO, ce statut décrit le résultat du workflow synthétique ; il ne prouve pas un rétablissement en production. Le stage VERIFY doit être accompagné de mesures explicites pour constituer une vérification métier."
    elif final_status == "BLOCKED":
        closing = "Run bloqué. Une intervention humaine ou des éléments complémentaires sont nécessaires."
    else:
        closing = "Traitement en cours ou état final non confirmé."
    out.extend([
        "<h3>Conclusion opérationnelle</h3><p>" + html.escape(closing) + "</p>",
        "<p><em>Source : snapshots Core/ledger. Les données DEMO, REPLAY et STORY restent synthétiques et ne constituent pas une preuve de production.</em></p>",
        _END,
    ])
    return "".join(out)


def merge_report(existing_content, report_html):
    """Replace only the AIOps2-owned section and preserve the original ticket text."""
    existing = existing_content if isinstance(existing_content, str) else ""
    start = existing.find(_START)
    if start >= 0:
        end = existing.find(_END, start)
        if end >= 0:
            end += len(_END)
            return existing[:start] + report_html + existing[end:]
    return (existing.rstrip() + "<hr>" if existing.strip() else "") + report_html
