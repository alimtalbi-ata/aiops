import json
import datetime
import urllib.request
import re
from portal.glpi_client import GLPIClient

NOW = datetime.datetime.now(
    datetime.timezone.utc
).isoformat()

CORE = "http://aiops2-core:810"
TICKET_ID = 147

result = {
    "schema": "aiops2.fs375.correlation.v1",
    "collected_at": NOW,
    "ticket_id": TICKET_ID,
    "confirmed_run_ids": [],
    "candidate_run_ids": [],
    "critic_decision": "NOT_VERIFIED",
    "policy_decision": "NOT_VERIFIED",
    "hitl_authorized": False,
    "remediation_executed": False,
    "sources": [],
    "limitations": []
}

def fetch(path):
    with urllib.request.urlopen(
        CORE + path, timeout=5
    ) as response:
        return json.load(response)

def records(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "data", "runs", "incidents"):
            if isinstance(data.get(key), list):
                return data[key]
    return []

def plain(value):
    return re.sub(
        r"<[^>]+>", " ", str(value or "")
    )

client = GLPIClient()

ticket = client.get_ticket(TICKET_ID)
followups = client._call(
    "GET",
    f"Ticket/{TICKET_ID}/ITILFollowup"
)

if isinstance(followups, dict):
    followups = followups.get("data", [])

ticket_text = " ".join([
    plain(ticket.get("name")),
    plain(ticket.get("content"))
] + [
    plain(x.get("content"))
    for x in followups
])

result["sources"].append(
    f"GLPI Ticket/{TICKET_ID}"
)

# Ticket evidence can contain historical RUN references.
ticket_run_ids = set(re.findall(
    r"RUN-[A-Z0-9]{12,24}",
    ticket_text
))

try:
    runs = records(fetch("/api/runs"))
    result["sources"].append(
        "core:/api/runs"
    )
except Exception as exc:
    runs = []
    result["limitations"].append(
        "Core runs unavailable: " +
        type(exc).__name__
    )

try:
    incidents = records(
        fetch("/api/incidents")
    )
    result["sources"].append(
        "core:/api/incidents"
    )
except Exception as exc:
    incidents = []
    result["limitations"].append(
        "Core incidents unavailable: " +
        type(exc).__name__
    )

for run in runs:
    if not isinstance(run, dict):
        continue

    run_id = str(
        run.get("run_id")
        or run.get("id")
        or ""
    )

    if not run_id.startswith("RUN-"):
        continue

    # Only explicit ticket references in a Core run
    # can confirm an association.
    linked_ticket = str(
        run.get("glpi_ticket_id")
        or run.get("ticket_id")
        or ""
    )

    if linked_ticket == str(TICKET_ID):
        result["confirmed_run_ids"].append(
            run_id
        )
        continue

    # A RUN mentioned in GLPI is a candidate,
    # not automatically a confirmed link.
    if run_id in ticket_run_ids:
        result["candidate_run_ids"].append(
            run_id
        )

for incident in incidents:
    if not isinstance(incident, dict):
        continue

    if str(
        incident.get("glpi_ticket_id")
        or incident.get("ticket_id")
        or ""
    ) != str(TICKET_ID):
        continue

    result["sources"].append(
        "core:incident-with-ticket-reference"
    )

    incident_run = str(
        incident.get("run_id") or ""
    )

    if incident_run.startswith("RUN-"):
        result["candidate_run_ids"].append(
            incident_run
        )

result["confirmed_run_ids"] = sorted(set(
    result["confirmed_run_ids"]
))

result["candidate_run_ids"] = sorted(
    set(result["candidate_run_ids"])
    - set(result["confirmed_run_ids"])
)

if not result["confirmed_run_ids"]:
    result["limitations"].append(
        "No verified Core RUN linked to GLPI #147"
    )

result["limitations"].append(
    "Critic/Policy decisions require "
    "RUN-specific evidence; not inferred "
    "from historical runs."
)

result["limitations"].append(
    "No HITL authorization for deleting "
    "/fs-lab/aiops2-demo-fill.bin."
)

with open(
    "/tmp/fs375-correlation.json", "w"
) as f:
    json.dump(
        result, f,
        ensure_ascii=False,
        indent=2
    )

print(
    "FS375_CONFIRMED_RUNS",
    result["confirmed_run_ids"]
)

print(
    "FS375_CANDIDATE_RUNS",
    result["candidate_run_ids"]
)

print(
    "FS375_CRITIC",
    result["critic_decision"]
)

print(
    "FS375_POLICY",
    result["policy_decision"]
)
