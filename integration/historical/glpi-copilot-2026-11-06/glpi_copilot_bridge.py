#!/usr/bin/env python3
"""AIOps2 GLPI Copilot — contextual, read-only diagnostic assistant."""

import os
import re
import html
import json
import datetime
import urllib.request
from portal.glpi_client import GLPIClient

TAG = "AIOPS2-GLPI-COPILOT-V1"
LIMIT = int(os.getenv("AIOPS_COPILOT_TICKET_LIMIT", "100"))
MIN_ID = int(os.getenv("AIOPS_COPILOT_MIN_TICKET_ID", "147"))
COPILOT_URL = os.getenv(
    "AIOPS_COPILOT_URL",
    "http://aiops2-copilot:814"
).rstrip("/")


def log(*args):
    print(
        datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        *args,
        flush=True
    )


def plain(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return " ".join(html.unescape(value).split())


def rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("data", "items"):
            if isinstance(value.get(key), list):
                return value[key]
    raise RuntimeError("Unexpected GLPI response")


def followups(client, ticket_id):
    """Read every GLPI followup page without losing idempotence markers."""
    page_size = 100
    offset = 0
    collected = []
    seen = set()

    while True:
        page = rows(client._call(
            "GET",
            f"Ticket/{ticket_id}/ITILFollowup",
            params={"range": f"{offset}-{offset + page_size - 1}"}
        ))

        if not page:
            break

        for item in page:
            fid = int(item.get("id", 0))
            if fid <= 0 or fid in seen:
                continue
            seen.add(fid)
            collected.append(item)

        if len(page) < page_size:
            break

        offset += page_size

    return collected


def post(client, ticket_id, content, marker):
    body = (
        '<div style="border-left:4px solid #2563eb;'
        'padding:12px;background:#eff6ff">'
        '<p><strong>🤖 AIOps2 Copilot</strong></p>'
        + content
        + '<p style="font-size:11px;color:#64748b">'
        + html.escape(marker)
        + "</p></div>"
    )

    result = client._call(
        "POST",
        "ITILFollowup",
        json={"input": [{
            "itemtype": "Ticket",
            "items_id": ticket_id,
            "content": body,
            "is_private": 0
        }]}
    )

    log("POSTED", ticket_id, result)


def paragraph(value):
    return "<p>" + html.escape(str(value)) + "</p>"


def section(title, body):
    return (
        '<h4 style="color:#1d4ed8;margin-bottom:5px">'
        + html.escape(title)
        + "</h4>"
        + paragraph(body)
    )


def query_service(question, run_id):
    payload = {
        "question": question[:2000],
        "run_id": run_id
    }

    request = urllib.request.Request(
        COPILOT_URL + "/api/copilot/query",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=12
        ) as response:
            data = json.load(response)

        answer = str(data.get("answer", "")).strip()

        if not answer:
            raise ValueError("Empty Copilot answer")

        return {
            "available": True,
            "answer": answer[:3500],
            "sources": data.get("sources", []),
            "limitations": data.get("limitations", [])
        }

    except Exception as exc:
        return {
            "available": False,
            "answer": (
                "Service Copilot indisponible : "
                + type(exc).__name__
            ),
            "sources": [],
            "limitations": [
                "Aucune réponse IA inventée."
            ]
        }


def filesystem_context(ticket, history):
    title = plain(ticket.get("name"))
    description = plain(ticket.get("content"))

    # Only evidence present in the ticket is used.
    # Never substitute historical lab measurements for live state.
    evidence = []

    combined = " ".join(
        [title, description]
        + [plain(x.get("content")) for x in history]
    )

    if "/fs-lab" in combined:
        evidence.append(
            "Filesystem concerné : /fs-lab."
        )

    usage = re.search(
        r"(?:/fs-lab.{0,100}?)?\\b(\\d{1,3})\\s*%",
        combined,
        re.I
    )

    if usage:
        evidence.append(
            "Occupation mentionnée dans GLPI : "
            + usage.group(1)
            + " %."
        )

    filename = (
        "/fs-lab/aiops2-demo-fill.bin"
    )

    if filename in combined:
        evidence.append(
            "Fichier mentionné dans les preuves : "
            + filename
        )

    size = re.search(
        r"\\b11534336\\b|\\b11264\\b",
        combined
    )

    if size:
        evidence.append(
            "Taille du fichier documentée dans GLPI : "
            "11 MiB environ."
        )

    run = re.search(
        r"\\bRUN-[A-Z0-9]{12,24}\\b",
        combined
    )

    return {
        "title": title,
        "description": description,
        "evidence": evidence,
        "run_id": run.group(0) if run else None
    }



def answer_ticket(ticket, history, question):
    ctx = filesystem_context(ticket, history)

    output = section(
        "Ticket analysé",
        "GLPI #" + str(ticket["id"]) +
        " — " + ctx["title"]
    )

    output += section(
        "Question du technicien",
        question[:1000]
    )

    fs_question = (
        "/fs-lab" in (
            ctx["title"] + " " +
            ctx["description"] + " " +
            question
        ).lower()
        or "filesystem" in (
            ctx["title"] + " " + question
        ).lower()
    )

    if fs_question:
        try:
            import json
            from datetime import datetime, timezone

            with open(
                "/tmp/fs373-evidence.json"
            ) as f:
                ev=json.load(f)

            timestamp=datetime.fromisoformat(
                ev["collected_at"]
            )

            age=(
                datetime.now(timezone.utc)
                - timestamp
            ).total_seconds()

            if age < 0 or age > 600:
                raise ValueError(
                    "Evidence older than 10 minutes"
                )

            output += section(
                "Mesures réelles du laboratoire",
                "Filesystem : " +
                ev["filesystem"] +
                " | Occupation : " +
                str(ev["used_percent"]) + " %" +
                " | Utilisé : " +
                str(ev["used_kib"]) + " KiB" +
                " | Disponible : " +
                str(ev["available_kib"]) + " KiB"
            )

            output += section(
                "Fichier dominant",
                ev["file"] +
                " | Observation du : " +
                str(ev["collected_at"])
            )

            output += section(
                "Diagnostic",
                "La saturation est associée à "
                "l'occupation observée du fichier "
                "dans le laboratoire isolé. "
                "Cette observation ne démontre pas "
                "une panne de production ni que le "
                "fichier peut être supprimé."
            )

            output += section(
                "Preuves techniques",
                "df : " + ev["df_raw"] +
                " | du : " + ev["du_raw"] +
                " | ls : " + ev["ls_raw"]
            )

            output += section(
                "Informations manquantes",
                "Validation du propriétaire du fichier, "
                "politique de rétention, dépendances, "
                "autorisation HITL propre à cette action, "
                "RUN corrélé et état actuel Prometheus."
            )

            output += section(
                "Sources",
                "GLPI Ticket/" +
                str(ticket["id"]) +
                " ; docker exec aiops2-fs-lab ; " +
                ev["collected_at"]
            )

        except Exception as exc:
            output += section(
                "Preuves filesystem indisponibles",
                type(exc).__name__ +
                " : mesure actuelle non confirmée."
            )

    else:
        service=query_service(
            question,
            ctx["run_id"]
        )

        output += section(
            "Réponse Copilot",
            service["answer"]
        )

        output += section(
            "Sources déclarées",
            ", ".join(
                map(str,service["sources"])
            ) or "Aucune source confirmée"
        )


    # FS374: independent, timestamped service evidence.
    try:
        import json
        from datetime import datetime, timezone

        with open(
            "/tmp/fs374-services.json"
        ) as f:
            services = json.load(f)

        stamp = datetime.fromisoformat(
            services["collected_at"]
        )

        age = (
            datetime.now(timezone.utc) - stamp
        ).total_seconds()

        if age < 0 or age > 600:
            raise ValueError(
                "Service snapshot expired"
            )

        summaries = []

        for name, source in services[
            "sources"
        ].items():
            if source.get("available"):
                value = source.get("value", {})
                summaries.append(
                    name + " : accessible ; " +
                    str(value)[:900]
                )
            else:
                summaries.append(
                    name + " : inaccessible (" +
                    str(source.get("error")) + ")"
                )

        output += section(
            "Corrélation Core / métriques",
            " | ".join(summaries)
        )

        output += section(
            "Critic / Policy : niveau de preuve",
            "L'accessibilité des endpoints ne "
            "prouve pas à elle seule la décision "
            "Critic ou Policy de cet incident. "
            "La décision propre au RUN est "
            "contrôlée séparément auprès de Core. "
            "Aucune autorisation HITL déduite "
            "des anciens tickets."
        )

    except Exception as exc:
        output += section(
            "Corrélation Core / métriques",
            "Indisponible ou périmée : " +
            type(exc).__name__ +
            ". Aucune donnée historique "
            "présentée comme actuelle."
        )


    # FS401: verify the ticket RUN directly against Core.
    try:
        title = plain(ticket.get("name"))
        description = plain(ticket.get("content"))

        title_runs = set(re.findall(
            r"RUN-[A-Z0-9]{12,24}", title
        ))

        report_runs = set(re.findall(
            r"RUN-[A-Z0-9]{12,24}", description
        ))

        if len(title_runs) != 1:
            raise ValueError("Expected exactly one RUN in ticket title")

        run_id = next(iter(title_runs))

        if run_id not in report_runs:
            raise ValueError("RUN absent from GLPI report")

        incident_ids = set(re.findall(
            r"INC-[A-Z0-9-]{8,120}", description
        ))

        if len(incident_ids) != 1:
            raise ValueError("Incident reference ambiguous in GLPI")

        expected_incident = next(iter(incident_ids))

        core_url = os.getenv(
            "AIOPS_CORE_URL",
            "http://aiops2-core:810"
        ).rstrip("/")

        with urllib.request.urlopen(
            core_url + "/api/runs/" + run_id,
            timeout=8
        ) as response:
            detail = json.load(response)

        run = detail["run"]

        if run.get("run_id") != run_id:
            raise ValueError("Core RUN identity mismatch")

        if run.get("incident_id") != expected_incident:
            raise ValueError("Core incident identity mismatch")

        events = detail.get("events", [])

        critic_events = [
            event for event in events
            if event.get("stage") == "DGX_CRITIC"
            and event.get("event_type") == "CRITIC_COMPLETED"
        ]

        if len(critic_events) != 1:
            raise ValueError("Critic decision not uniquely verified")

        critic = critic_events[0]

        if (
            run.get("status") == "BLOCKED"
            and critic.get("status") == "BLOCKED"
            and critic.get("decision") == "HUMAN_APPROVAL"
        ):
            critic_text = (
                "BLOCKED / HUMAN_APPROVAL "
                "(événement Core vérifié)"
            )
        else:
            critic_text = (
                "Décision Core : "
                + str(critic.get("status"))
                + " / "
                + str(critic.get("decision"))
                + " ; aucune autorisation déduite."
            )

        stages = {
            item.get("stage"): item.get("state")
            for item in detail.get("stages", [])
        }

        policy_state = stages.get("POLICY", "UNKNOWN")
        hitl_state = stages.get("HITL", "UNKNOWN")

        output += section(
            "Corrélation GLPI / Core vérifiée",
            "Ticket GLPI #" + str(ticket["id"])
            + " | RUN : " + run_id
            + " | Incident : " + expected_incident
            + " | État Core : " + str(run.get("status"))
        )

        output += section(
            "Décision Critic vérifiée",
            critic_text
        )

        output += section(
            "Étapes Policy / HITL",
            "Policy : " + str(policy_state)
            + " | HITL : " + str(hitl_state)
            + ". PENDING signifie non exécuté, "
            "pas approuvé."
        )

    except Exception as exc:
        output += section(
            "Corrélation GLPI / Core",
            "Non vérifiable directement : "
            + type(exc).__name__
            + ". Aucune décision de sécurité présumée."
        )

    output += section(
        "Policy / HITL",
        "Diagnostic uniquement. "
        "Aucune suppression, aucune validation "
        "HITL, aucune résolution automatique."
    )

    return output


def extract_copilot_question(content):
    text = plain(content)

    match = re.search(
        r"(?<![\w@])@(?:copilote|copilot)(?![\w])",
        text,
        flags=re.IGNORECASE
    )

    if match is None:
        return None

    return text[match.end():].strip().lstrip(":,- ").strip()



def process_ticket(client, ticket):
    tid = int(ticket["id"])

    if str(ticket.get("is_deleted", 0)) == "1":
        return

    history = followups(client, tid)
    existing = [
        plain(item.get("content"))
        for item in history
    ]

    welcome = TAG + ":WELCOME:" + str(tid)

    if not any(welcome in x for x in existing):
        post(
            client,
            tid,
            section(
                "Copilot disponible",
                "Ajoutez un suivi public commençant "
                "par @copilot suivi de votre question."
            ),
            welcome
        )
        history = followups(client, tid)
        existing = [
            plain(item.get("content"))
            for item in history
        ]

    for item in sorted(
        history,
        key=lambda x: int(x.get("id", 0))
    ):
        fid = int(item.get("id", 0))
        content = plain(item.get("content"))
        marker = TAG + ":ANSWER:" + str(fid)

        if any(marker in x for x in existing):
            continue

        if TAG in content:
            continue

        # FS411D: standalone mentions anywhere in a followup.
        question = extract_copilot_question(content)

        if question is None:
            continue

        log("QUESTION_DETECTED", tid, fid)

        if question:
            response = answer_ticket(
                ticket,
                history,
                question
            )
        else:
            response = paragraph(
                "Veuillez préciser votre question."
            )

        post(client, tid, response, marker)
        existing.append(marker)

def main():
    client = GLPIClient()

    if not client.configured:
        raise RuntimeError(
            "GLPI credentials unavailable"
        )

    tickets = rows(client._call(
        "GET",
        "Ticket",
        params={
            "range": f"0-{LIMIT-1}",
            "sort": "id",
            "order": "DESC"
        }
    ))

    log("VISIBLE_TICKETS", len(tickets))

    processed = 0

    for item in sorted(
        tickets,
        key=lambda x: int(x.get("id", 0)),
        reverse=True
    ):
        ticket_id = int(item.get("id", 0))

        if ticket_id < MIN_ID:
            continue

        try:
            ticket = client.get_ticket(ticket_id)
            process_ticket(client, ticket)
            processed += 1
        except Exception as exc:
            log(
                "TICKET_ERROR",
                ticket_id,
                type(exc).__name__,
                str(exc)[:200]
            )

    log("FINISHED", processed)


if __name__ == "__main__":
    main()
