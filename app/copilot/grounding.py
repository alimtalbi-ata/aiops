"""Deterministic, read-only ACME answer contracts; no generative claims."""
import re
from datetime import datetime, timezone

RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$")
INTENTS = {
    "runs_total": (
        "combien de runs", "nombre de runs", "combien d'executions",
        "how many runs", "run count",
    ),
    "open_incidents": (
        "combien d'incidents ouverts", "nombre d'incidents ouverts",
        "how many open incidents", "open incident count",
    ),
    "topology": (
        "combien de noeuds et de liens", "taille de la topologie",
        "how many topology nodes and edges", "topology size",
    ),
    "run_evidence": (
        "quelles preuves pour ce run", "preuves de ce run",
        "what evidence for this run", "run evidence",
    ),
}


def classify(question):
    """Only recognized complete questions are supported; appended instructions fail closed."""
    q = " ".join(question.casefold().strip().split()).strip(" ?!.")
    q = (q.replace("œ", "oe").replace("é", "e").replace("è", "e")
           .replace("ê", "e").replace("à", "a").replace("û", "u"))
    for intent, forms in INTENTS.items():
        if q in forms:
            return intent
    return None


def unknown(reason="NO_SUPPORTED_EVIDENCE"):
    return {
        "status": "UNKNOWN",
        "answer": "Information indisponible dans les sources ACME autorisées.",
        "sources": [],
        "confidence": None,
        "reason": reason,
        "actions_allowed": False,
    }


def _citation(endpoint, source_id, retrieved_at, synthetic=None):
    result = {
        "source_id": source_id,
        "endpoint": endpoint,
        "retrieved_at": retrieved_at,
    }
    if synthetic is not None:
        result["synthetic"] = synthetic
    return result


def snapshot_answer(intent, data, retrieved_at):
    """Answer only known schema fields from a trusted internal read-only API."""
    if not isinstance(data, dict):
        return unknown("INVALID_SOURCE_SCHEMA")
    if intent == "runs_total":
        key, endpoint, source = "runs_total", "/api/dashboard", "core:dashboard"
        label = "Runs enregistrés"
    elif intent == "open_incidents":
        key, endpoint, source = "open_incidents", "/api/dashboard", "core:dashboard"
        label = "Incidents ouverts"
    elif intent == "topology":
        nodes, edges = data.get("nodes"), data.get("edges")
        if type(nodes) is not int or type(edges) is not int or min(nodes, edges) < 0:
            return unknown("INVALID_SOURCE_SCHEMA")
        return {
            "status": "GROUNDED",
            "answer": f"Topologie ACME : {nodes} nœuds et {edges} relations (instantané du jumeau).",
            "sources": [_citation("/api/twin/summary", "twin:summary", retrieved_at)],
            "confidence": None,
            "actions_allowed": False,
        }
    else:
        return unknown("UNSUPPORTED_QUESTION")
    count = data.get(key)
    if type(count) is not int or count < 0:
        return unknown("INVALID_SOURCE_SCHEMA")
    return {
        "status": "GROUNDED",
        "answer": f"{label} : {count} (instantané Core).",
        "sources": [_citation(endpoint, source, retrieved_at)],
        "confidence": None,
        "actions_allowed": False,
    }


def evidence_answer(run_id, run, data, retrieved_at):
    """Return only IDs of explicitly synthetic evidence scoped to the requested run."""
    if not RUN_ID.fullmatch(run_id):
        return unknown("INVALID_RUN_ID")
    record = run.get("run") if isinstance(run, dict) else None
    if not isinstance(record, dict) or record.get("run_id") != run_id:
        return unknown("RUN_NOT_VERIFIED")
    if record.get("mode") not in ("DEMO", "REPLAY", "STORY"):
        return unknown("LIVE_ACCESS_NOT_QUALIFIED")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return unknown("INVALID_SOURCE_SCHEMA")
    sources = []
    for item in items:
        if not isinstance(item, dict):
            continue
        provenance = item.get("provenance")
        if not isinstance(provenance, dict):
            continue
        if provenance.get("run_id") != run_id or provenance.get("synthetic") is not True:
            continue
        eid, origin, known = item.get("evidence_id"), item.get("source"), item.get("known_at")
        if not all(isinstance(x, str) and x.strip() for x in (eid, origin, known)):
            continue
        if not RUN_ID.fullmatch(eid):
            continue
        sources.append({
            **_citation(f"/api/evidence/{eid}", eid, retrieved_at, synthetic=True),
            "origin": origin,
            "known_at": known,
        })
    if not sources:
        return unknown("NO_SCOPED_SYNTHETIC_EVIDENCE")
    return {
        "status": "GROUNDED",
        "answer": f"{len(sources)} preuve(s) synthétique(s) identifiée(s) pour le run {run_id}. Les contenus ne sont pas interprétés.",
        "sources": sources[:30],
        "confidence": None,
        "actions_allowed": False,
    }


def now_utc():
    return datetime.now(timezone.utc).isoformat()
