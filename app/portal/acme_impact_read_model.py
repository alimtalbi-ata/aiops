"""Read-only, synthetic ACME SAN P1 -> Payments P2 view on the existing portal.

No upstream service is contacted. Run IDs are deterministic labels derived from
the exact local fixture bytes, not backend execution IDs. Missing ticket/timestamp
fields are explicit and never synthesized.
"""
from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from portal.acme_fixture_contract import load_fixture_bytes, validate_fixture

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
FIXTURE_PATH = Path(__file__).resolve().with_name("acme-fixtures.json")

HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'none'; connect-src 'none'; img-src 'none'; style-src 'none'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}


def build_acme_impact_read_model() -> dict[str, Any]:
    """Build a deterministic simulation view from the exact validated local bytes."""
    if FIXTURE_PATH.is_symlink() or not FIXTURE_PATH.is_file():
        raise ValueError("synthetic ACME fixture is unavailable")
    raw = FIXTURE_PATH.read_bytes()
    fixture = load_fixture_bytes(raw)
    report = validate_fixture(fixture)
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "schema": "aiops.synthetic-impact-read-model.v1",
        "entrypoint": "http://10.79.94.202:17777/",
        "run_id": "SIM-ACME-" + digest[:16].upper(),
        "run_id_provenance": "DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN",
        "incident_id": report["source_incident_id"],
        "incident_role": "SOURCE_SAN_P1",
        "impact_incident_id": report["target_incident_id"],
        "impact_role": "PAYMENTS_P2",
        "ticket_id": None,
        "ticket_id_provenance": "ABSENT_NO_GLPI_WRITE",
        "event_timestamp_utc": None,
        "timestamp_provenance": "ABSENT_NO_RUNTIME_EVENT",
        "source_artifact": "app/portal/acme-fixtures.json",
        "source_sha256": digest,
        "ci_count": report["ci_count"],
        "incident_count": report["incident_count"],
        "impact_path": report["impact_path"],
        "provenance": "SIMULATED_TARGET",
        "evidence_source": "LOCAL_SYNTHETIC_FIXTURE",
        "runtime_evidence_present": False,
        "runtime_attested": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }


def _load_or_503() -> dict[str, Any]:
    try:
        return build_acme_impact_read_model()
    except (OSError, UnicodeError, ValueError, ImportError, AttributeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="synthetic_impact_fixture_unavailable_or_invalid",
        ) from exc


@router.get("/api/demo/acme-impact", name="synthetic_acme_impact_read_model")
def acme_impact_json():
    """Return the synthetic impact graph and explicit provenance gaps."""
    return JSONResponse(content=_load_or_503(), headers=HEADERS)


@router.get("/demo/acme-impact", response_class=HTMLResponse, name="synthetic_acme_impact_page")
def acme_impact_page():
    """Serve a local HTML snapshot; no scripts, forms, links or upstream calls."""
    model = _load_or_503()
    path = " → ".join(str(part) for part in model["impact_path"])
    rows = [
        ("Run ID (simulation)", model["run_id"], model["run_id_provenance"]),
        ("Incident source SAN P1", model["incident_id"], model["provenance"]),
        ("Incident d'impact Payments P2", model["impact_incident_id"], model["provenance"]),
        ("Ticket GLPI", "ABSENT", model["ticket_id_provenance"]),
        ("Horodatage d'événement", "ABSENT", model["timestamp_provenance"]),
        ("Chemin d'impact calculé", path, "LOCAL_SYNTHETIC_DEPENDENCY_GRAPH"),
        ("SHA-256 de la source", model["source_sha256"], "EXACT_FIXTURE_BYTES"),
        ("Source", model["source_artifact"], model["evidence_source"]),
        ("Qualification runtime", "NON", "runtime_attested=false"),
    ]
    table_rows = "".join(
        "<tr><th scope=\"row\">" + html.escape(str(label), quote=True)
        + "</th><td>" + html.escape(str(value), quote=True)
        + "</td><td>" + html.escape(str(provenance), quote=True) + "</td></tr>"
        for label, value, provenance in rows
    )
    body = (
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>ACME — impact SAN P1 vers Payments P2 (simulation)</title>"
        "</head><body><main><h1>ACME — SAN P1 → Payments P2</h1>"
        "<p><strong>SIMULATION LOCALE UNIQUEMENT.</strong> Aucun incident runtime, "
        "ticket GLPI, capture applicative, appel backend ou événement horodaté n'est créé. "
        "Le run_id affiché est dérivé des octets du fixture, pas d'un run exécuté.</p>"
        "<table><caption>Identifiants, provenance et trous de preuve</caption>"
        "<thead><tr><th scope=\"col\">Champ</th><th scope=\"col\">Valeur</th>"
        "<th scope=\"col\">Origine / qualification</th></tr></thead>"
        "<tbody>" + table_rows + "</tbody></table>"
        "<p>Remédiation LIVE autorisée : NON. Horodatage et ticket non disponibles "
        "tant qu'aucune intégration runtime authentifiée n'a été qualifiée.</p>"
        "</main></body></html>"
    )
    return HTMLResponse(content=body, headers=HEADERS)
