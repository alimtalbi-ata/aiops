import json
import re
import datetime
import urllib.request
from pathlib import Path

from portal.glpi_client import GLPIClient

TICKET_ID = 147
CORE = "http://aiops2-core:810"
OUT = Path("/tmp/fs376-audit.json")

now = datetime.datetime.now(
    datetime.timezone.utc
).isoformat()

report = {
    "schema": "aiops2.fs376.audit.v1",
    "collected_at": now,
    "ticket_id": TICKET_ID,
    "filesystem": "/fs-lab",
    "status": "NOT_CORRELATED",
    "confirmed_links": [],
    "filesystem_candidates": [],
    "critic_evidence": [],
    "policy_evidence": [],
    "sources": [],
    "errors": [],
    "hitl_authorized": False,
    "remediation_executed": False,
}

def fetch(path):
    with urllib.request.urlopen(
        CORE + path, timeout=5
    ) as response:
        return json.load(response)

def extract_records(obj, preferred=()):
    if isinstance(obj, list):
        return obj

    if isinstance(obj, dict):
        for key in preferred + (
            "items", "data", "results",
            "runs", "incidents"
        ):
            value = obj.get(key)

            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                nested = extract_records(
                    value, ()
                )
                if nested:
                    return nested

    return []

def text(obj):
    return json.dumps(
        obj, ensure_ascii=False,
        default=str
    )

def explicit_ticket_reference(obj):
    if not isinstance(obj, dict):
        return False

    # Only exact structured references count.
    for key in (
        "ticket_id",
        "glpi_ticket_id",
        "glpi_id"
    ):
        if str(obj.get(key, "")) == str(
            TICKET_ID
        ):
            return True

    return False

def run_id_of(obj):
    if not isinstance(obj, dict):
        return None

    for key in ("run_id", "id"):
        value = str(obj.get(key, ""))

        if re.fullmatch(
            r"RUN-[A-Z0-9]+", value
        ):
            return value

    return None

def incident_id_of(obj):
    if not isinstance(obj, dict):
        return None

    for key in ("incident_id", "id"):
        value = obj.get(key)

        if value is not None:
            return str(value)

    return None

def compact(obj, limit=3500):
    return text(obj)[:limit]

client = GLPIClient()

try:
    ticket = client.get_ticket(TICKET_ID)

    report["ticket_title"] = ticket.get(
        "name", ""
    )

    report["sources"].append(
        "GLPI:Ticket/147"
    )
except Exception as exc:
    report["errors"].append(
        "GLPI:" + repr(exc)
    )

try:
    runs = extract_records(
        fetch("/api/runs"),
        ("runs",)
    )

    report["sources"].append(
        "Core:/api/runs"
    )
except Exception as exc:
    runs = []
    report["errors"].append(
        "Core runs:" + repr(exc)
    )

try:
    incidents = extract_records(
        fetch("/api/incidents"),
        ("incidents",)
    )

    report["sources"].append(
        "Core:/api/incidents"
    )
except Exception as exc:
    incidents = []
    report["errors"].append(
        "Core incidents:" + repr(exc)
    )

# Build structured incident references.
linked_incidents = {}

for incident in incidents:
    if not isinstance(incident, dict):
        continue

    incident_id = incident_id_of(incident)

    if explicit_ticket_reference(
        incident
    ):
        if incident_id:
            linked_incidents[
                incident_id
            ] = incident

        report["confirmed_links"].append({
            "kind": "ticket_to_incident",
            "incident_id": incident_id,
            "evidence": compact(incident)
        })

    elif "/fs-lab" in text(incident):
        report[
            "filesystem_candidates"
        ].append({
            "kind": "incident",
            "incident_id": incident_id,
            "evidence": compact(incident)
        })

for run in runs:
    if not isinstance(run, dict):
        continue

    run_id = run_id_of(run)

    if not run_id:
        continue

    linked_incident_id = str(
        run.get("incident_id", "")
    )

    direct_link = explicit_ticket_reference(
        run
    )

    indirect_link = (
        bool(linked_incident_id)
        and linked_incident_id
        in linked_incidents
    )

    if direct_link or indirect_link:
        report["confirmed_links"].append({
            "kind": "ticket_to_run",
            "run_id": run_id,
            "link_type": (
                "direct"
                if direct_link
                else "via_incident"
            ),
            "evidence": compact(run)
        })

        # Decisions are evidence only when
        # carried by this correlated RUN.
        for key in (
            "critic",
            "critic_decision",
            "dgx_critic"
        ):
            if key in run:
                report[
                    "critic_evidence"
                ].append({
                    "run_id": run_id,
                    "field": key,
                    "value": run[key]
                })

        for key in (
            "policy",
            "policy_decision",
            "policy_result"
        ):
            if key in run:
                report[
                    "policy_evidence"
                ].append({
                    "run_id": run_id,
                    "field": key,
                    "value": run[key]
                })

    elif "/fs-lab" in text(run):
        report[
            "filesystem_candidates"
        ].append({
            "kind": "run",
            "run_id": run_id,
            "evidence": compact(run)
        })

confirmed_run_ids = sorted({
    link["run_id"]
    for link in report["confirmed_links"]
    if link["kind"] == "ticket_to_run"
})

report["confirmed_run_ids"] = (
    confirmed_run_ids
)

if confirmed_run_ids:
    report["status"] = (
        "RUN_LINK_CONFIRMED"
    )
elif report["confirmed_links"]:
    report["status"] = (
        "INCIDENT_LINK_ONLY"
    )
elif report["filesystem_candidates"]:
    report["status"] = (
        "FILESYSTEM_CANDIDATES_ONLY"
    )

report["limitations"] = [
    "Filesystem similarity does not "
    "prove GLPI-to-RUN identity.",
    "Critic/Policy are not inferred "
    "from uncorrelated historical RUNs.",
    "No HITL authorization is granted "
    "by this audit."
]

OUT.write_text(
    json.dumps(
        report,
        ensure_ascii=False,
        indent=2
    )
)

print(
    "FS376_STATUS",
    report["status"]
)

print(
    "FS376_CONFIRMED_RUNS",
    confirmed_run_ids
)

print(
    "FS376_FS_CANDIDATES",
    len(
        report["filesystem_candidates"]
    )
)

print(
    "FS376_CRITIC_EVIDENCE",
    len(report["critic_evidence"])
)

print(
    "FS376_POLICY_EVIDENCE",
    len(report["policy_evidence"])
)

print(
    "FS376_ERRORS",
    len(report["errors"])
)
