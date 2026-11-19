"""Read-only, synthetic ACME SAN P1 -> Payments P2 view on the existing portal.

No upstream service is contacted. Run IDs are deterministic labels derived from
the exact local fixture bytes, not backend execution IDs. Real ticket/timestamp
fields stay absent; separate synthetic ticket/checkpoint labels are explicitly
marked as simulation and must never be treated as runtime evidence.
"""
from __future__ import annotations

import hashlib
import html
import os
import stat
from pathlib import Path
from typing import Any

from portal.acme_fixture_contract import load_fixture_bytes, validate_fixture
from portal.acme_twin_provenance import build_twin_evidence
from portal.acme_twin_consumer import project_twin_consumer
from portal.acme_signal_context import build_signal_context

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
FIXTURE_PATH = Path(__file__).resolve().with_name("acme-fixtures.json")
MAX_FIXTURE_BYTES = 256 * 1024

HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'none'; connect-src 'none'; img-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}


def _read_fixture_bytes_safely(path: Path) -> bytes:
    """Read one bounded regular file without following a symlink or trusting a pathname twice.

    The digest and schema validation downstream operate on the same byte string
    returned here. Platforms lacking O_NOFOLLOW fail closed rather than silently
    weakening the fixture trust boundary.
    """
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ValueError("platform cannot safely open the synthetic fixture")
    flags = os.O_RDONLY | nofollow
    flags |= getattr(os, "O_CLOEXEC", 0)
    # Avoid blocking if an unexpected FIFO is substituted for the fixture.
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError("synthetic fixture cannot be opened safely") from exc

    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("synthetic fixture must be a regular file")
        if before.st_size < 0 or before.st_size > MAX_FIXTURE_BYTES:
            raise ValueError("synthetic fixture exceeds size limit")

        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_FIXTURE_BYTES + 1)

        after = os.fstat(fd)
        stable_before = (
            before.st_dev, before.st_ino, before.st_mode, before.st_size,
            before.st_mtime_ns, before.st_ctime_ns,
        )
        stable_after = (
            after.st_dev, after.st_ino, after.st_mode, after.st_size,
            after.st_mtime_ns, after.st_ctime_ns,
        )
        if stable_before != stable_after or len(raw) != after.st_size:
            raise ValueError("synthetic fixture changed during read")
        if len(raw) > MAX_FIXTURE_BYTES:
            raise ValueError("synthetic fixture exceeds size limit")
        return raw
    finally:
        os.close(fd)


def build_acme_impact_read_model() -> dict[str, Any]:
    """Build a deterministic simulation view from the exact validated local bytes."""
    raw = _read_fixture_bytes_safely(FIXTURE_PATH)
    fixture = load_fixture_bytes(raw)
    report = validate_fixture(fixture)
    digest = hashlib.sha256(raw).hexdigest()
    model = {
        "schema": "aiops.synthetic-impact-read-model.v1",
        "twin_evidence": build_twin_evidence(raw),
        "entrypoint": "/",
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
        # Stable scenario metadata is deliberately separate from real GLPI/runtime fields.
        "simulation_ticket_id": "SIM-GLPI-" + digest[:12].upper(),
        "simulation_ticket_provenance": "SYNTHETIC_LABEL_NOT_A_GLPI_TICKET",
        "simulation_checkpoint_timestamp_utc": "2026-10-25T09:00:00Z",
        "simulation_timestamp_provenance": "FIXED_SCENARIO_CLOCK_NOT_RUNTIME_EVENT",
        "source_artifact": "app/portal/acme-fixtures.json",
        "source_sha256": digest,
        "ci_count": report["ci_count"],
        "incident_count": report["incident_count"],
        "impact_path": report["impact_path"],
        "affected_ci_ids": report["affected_ci_ids"],
        "affected_cis": report["affected_cis"],
        "provenance": "SIMULATED_TARGET",
        "evidence_source": "LOCAL_SYNTHETIC_FIXTURE",
        "checkpoint_evidence": [
            {
                "cue": cue,
                "service": service,
                "view": view,
                "required_state": required_state,
                "status": "MISSING",
                "screenshot_sha256": None,
                "event_timestamp_utc": None,
                "runtime_authenticated": False,
                "source": "CHECKPOINT_CONTRACT_ONLY_NO_CAPTURE",
            }
            for cue, service, view, required_state in (
                ("detect", "grafana", "alert_dashboard", "firing"),
                ("correlate", "n8n", "ingress_execution", "completed"),
                ("enrich", "n8n", "context_execution", "completed"),
                ("analyze", "n8n", "analyst_critic_execution", "completed"),
                ("ticket", "glpi", "incident_ticket", "open"),
                ("approve", "glpi", "hitl_decision", "approved_simulation_only"),
                ("simulate", "n8n", "simulation_execution", "completed"),
                ("verify", "grafana", "recovery_dashboard", "recovered"),
                ("close", "glpi", "incident_followups", "closed"),
            )
        ],
        "decision_preview": {
            "provider": "DETERMINISTIC_RULES_NOT_LLM",
            "analyst": {
                "status": "HYPOTHESIS_ONLY",
                "summary": "Le SAN P1 peut expliquer l'impact Payments P2 via le chemin de dépendances calculé.",
                "next_checks": [
                    "Vérifier l'état de la fabric SAN et les chemins redondants",
                    "Confirmer le mapping du volume vers la VM et l'application",
                    "Comparer les observations runtime avant toute conclusion",
                ],
            },
            "critic": {
                "decision": "HOLD_FOR_HUMAN_REVIEW",
                "reason": "Aucune télémétrie runtime ni preuve indépendante n'est présente dans ce scénario.",
            },
            "policy": {
                "decision": "DENY_LIVE_ACTION",
                "reason": "La qualification runtime et l'autorisation LIVE sont absentes.",
            },
            "remediation_preview": [
                "Préparer une checklist de diagnostic SAN en lecture seule",
                "Vérifier le chemin redondant SAN-FABRIC-B sans supposer qu'il est sain",
                "Préparer un brouillon de ticket hors GLPI, sans écriture backend",
                "Demander une revue humaine avant toute action opérationnelle",
            ],
            "live_execution": False,
            "backend_writes": False,
        },
        "runtime_evidence_present": False,
        "runtime_attested": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }
    model["twin_consumer"] = project_twin_consumer(model)
    model["signal_context"] = build_signal_context(model["twin_evidence"])
    return model


def _load_or_503() -> dict[str, Any]:
    try:
        return build_acme_impact_read_model()
    except (OSError, UnicodeError, ValueError, ImportError, AttributeError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(
            status_code=503,
            detail="synthetic_impact_fixture_unavailable_or_invalid",
        ) from exc


@router.get("/demo/acme-itil-readiness", response_class=HTMLResponse,
            name="synthetic_acme_itil_readiness_page")
def acme_itil_readiness_page():
    """Static, script-free operator view of missing ITIL proof."""
    from portal.acme_lifecycle_read_model import project_synthetic_incident_lifecycle
    from portal.acme_itil_readiness import assess_synthetic_itil_readiness
    try:
        readiness = assess_synthetic_itil_readiness(
            project_synthetic_incident_lifecycle(_load_or_503())
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_itil_readiness_unqualified") from exc
    rows = "".join(
        "<tr><th scope='row'>" + html.escape(t["transition"], quote=True)
        + "</th><td>" + html.escape(t["readiness"], quote=True)
        + "</td><td>" + html.escape(", ".join(t["missing_evidence"]), quote=True)
        + "</td><td>NON</td></tr>"
        for t in readiness["transitions"]
    )
    page = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>AIOPS2 — Préparation ITIL (DEMO)</title>"
        "<style>body{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #777;padding:.65rem;text-align:left}"
        "thead{background:#eee;color:#111}caption{text-align:left;font-weight:bold}"
        ".warning{border-left:5px solid #9a6700;padding:1rem;background:#fff7dd;color:#302400}"
        "</style></head><body><main>"
        "<h1>AIOPS2 — Préparation des transitions ITIL</h1>"
        "<p class='warning'><strong>SIMULATION LOCALE UNIQUEMENT — NO-GO LIVE.</strong> "
        "Aucune preuve runtime indépendante, aucune transition autorisée, "
        "aucune écriture GLPI ni exécution Temporal.</p>"
        "<p>Incident SAN P1 : <code>"
        + html.escape(readiness["source_incident_id"], quote=True)
        + "</code> · Impact Payments P2 : <code>"
        + html.escape(readiness["business_impact_incident_id"], quote=True)
        + "</code></p>"
        "<p>Prochaine étape : collecte en lecture seule de preuves runtime indépendantes. "
        "Checkpoints manquants : " + str(readiness["missing_unique_checkpoint_count"])
        + ".</p>"
        "<table><caption>Étapes et preuves manquantes</caption>"
        "<thead><tr><th>Transition</th><th>Qualification</th>"
        "<th>Preuves requises absentes</th><th>Autorisée</th></tr></thead>"
        "<tbody>" + rows + "</tbody></table></div>"
        "<p>Source SHA-256 : <code>"
        + html.escape(readiness["source_sha256"], quote=True)
        + "</code></p></main></body></html>"
    )
    return HTMLResponse(content=page, headers=HEADERS)


@router.get("/demo/acme-evidence-plan", response_class=HTMLResponse,
            name="synthetic_acme_evidence_plan_page")
def acme_evidence_plan_page():
    """Static operator checklist, no uploads, scripts or evidence acceptance."""
    from portal.acme_lifecycle_read_model import project_synthetic_incident_lifecycle
    from portal.acme_evidence_collection_plan import plan_synthetic_evidence_collection
    try:
        plan = plan_synthetic_evidence_collection(
            project_synthetic_incident_lifecycle(_load_or_503())
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_evidence_plan_unqualified") from exc
    rows = "".join(
        "<tr><th scope='row'>" + html.escape(req["checkpoint"], quote=True)
        + "</th><td>" + html.escape(req["phase"], quote=True)
        + "</td><td>" + html.escape(req["expected_source"], quote=True)
        + "</td><td>" + html.escape(req["required_evidence_type"], quote=True)
        + "</td><td>" + html.escape(", ".join(req["required_metadata"]), quote=True)
        + "</td><td>MISSING — NON VÉRIFIÉ</td></tr>"
        for req in plan["requests"]
    )
    page = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>AIOPS2 — Preuves requises (DEMO)</title>"
        "<style>body{font:16px system-ui,sans-serif;max-width:1150px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #777;padding:.65rem;text-align:left}"
        "thead{background:#eee;color:#111}.warning{border-left:5px solid #9a6700;"
        "padding:1rem;background:#fff7dd;color:#302400}</style></head><body><main>"
        "<h1>AIOPS2 — Plan de collecte des preuves</h1>"
        "<p class='warning'><strong>SIMULATION LOCALE UNIQUEMENT — NO-GO LIVE.</strong>"
        " Aucune preuve acceptée, aucune collecte automatique, aucun accès GLPI/Temporal."
        "</p><p>Incident : <code>"
        + html.escape(plan["incident_id"], quote=True)
        + "</code> · Impact métier : <code>"
        + html.escape(plan["business_impact_incident_id"], quote=True)
        + "</code></p>"
        "<table><caption>Checkpoints et exigences de preuve indépendante</caption>"
        "<thead><tr><th>Checkpoint</th><th>Phase</th><th>Source attendue</th>"
        "<th>Type de preuve</th><th>Métadonnées requises</th><th>État</th></tr></thead>"
        "<tbody>" + rows + "</tbody></table>"
        "<p>Preuves vérifiées : 0 / " + str(plan["requested_count"]) + "</p>"
        "<p>Source SHA-256 : <code>"
        + html.escape(plan["source_sha256"], quote=True)
        + "</code></p></main></body></html>"
    )
    return HTMLResponse(content=page, headers=HEADERS)


@router.get("/demo/acme-grafana-pilot-preview", response_class=HTMLResponse,
            name="synthetic_acme_grafana_pilot_preview")
def acme_grafana_pilot_preview_page():
    """Synthetic customer illustration; never a real Grafana observation."""
    import json
    from portal.grafana_readonly_evidence import collect_grafana_alert_readonly
    from portal.grafana_pilot_preview import preview_grafana_pilot_evidence
    from portal.grafana_pilot_preview_html import render_grafana_pilot_preview_html
    try:
        template_path = Path(__file__).resolve().with_name("acme-readonly-pilot-register.template.json")
        register = json.loads(template_path.read_text(encoding="utf-8"))
        observed = "2026-11-14T11:59:00Z"
        candidate = collect_grafana_alert_readonly(
            fetch_alert=lambda rule, tenant: {
                "rule_uid": rule, "tenant_id": tenant,
                "dashboard_uid": "acme-san-payments-synthetic",
                "state": "firing", "observed_at_utc": observed,
            }, rule_uid="acme-san-p1-synthetic", tenant_id="acme-synthetic",
            service_identity="LOCAL_SYNTHETIC_FIXTURE_NOT_AUTHENTICATED",
            max_age_seconds=300, now_utc="2026-11-14T12:00:00Z",
        )
        from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
        cockpit = project_synthetic_incident_cockpit(_load_or_503())
        preview = preview_grafana_pilot_evidence(register, candidate)
        preview["synthetic_scenario"] = {
            "incident_id": cockpit["incident_id"],
            "business_impact_incident_id": cockpit["business_impact_incident_id"],
            "source_sha256": cockpit["source_sha256"],
            "qualification": cockpit["overall_qualification"],
        }
        page = render_grafana_pilot_preview_html(preview)
    except (OSError, ValueError, KeyError, TypeError, HTTPException) as exc:
        raise HTTPException(status_code=503, detail="synthetic_grafana_pilot_preview_unqualified") from exc
    return HTMLResponse(content=page, headers=HEADERS)


@router.get("/demo/acme-incident-cockpit", response_class=HTMLResponse,
            name="synthetic_acme_incident_cockpit_page")
def acme_incident_cockpit_page():
    """Operator view of one validated synthetic incident snapshot."""
    from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
    from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html
    try:
        cockpit = project_synthetic_incident_cockpit(_load_or_503())
        page = render_synthetic_cockpit_html(cockpit)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_incident_cockpit_unqualified") from exc
    return HTMLResponse(content=page, headers=HEADERS)


@router.get("/api/demo/acme-itil-handoff-draft",
            name="synthetic_acme_itil_handoff_draft")
def acme_itil_handoff_draft_json():
    """Inert incident handoff draft: never a GLPI write request."""
    from portal.acme_itil_draft import build_synthetic_itil_handoff_draft
    try:
        draft = build_synthetic_itil_handoff_draft(_load_or_503())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_itil_draft_unqualified") from exc
    return JSONResponse(content=draft, headers=HEADERS)


@router.get("/api/demo/acme-incident-cockpit", name="synthetic_acme_incident_cockpit")
def acme_incident_cockpit_json():
    """One fixture snapshot, cross-checked incident-to-ITIL DEMO cockpit."""
    from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
    try:
        cockpit = project_synthetic_incident_cockpit(_load_or_503())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_incident_cockpit_unqualified") from exc
    return JSONResponse(content=cockpit, headers=HEADERS)


@router.get("/api/demo/acme-analyst-critic-review",
            name="synthetic_acme_analyst_critic_review")
def acme_analyst_critic_review_json():
    """Read-only Analyst/Critic evidence gap review; no LLM or execution."""
    from portal.acme_analyst_critic_review import review_synthetic_analyst_critic
    try:
        review = review_synthetic_analyst_critic(_load_or_503())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_analyst_critic_unqualified") from exc
    return JSONResponse(content=review, headers=HEADERS)


@router.get("/api/demo/acme-evidence-plan", name="synthetic_acme_evidence_plan")
def acme_evidence_plan_json():
    """Read-only requirements for independent proof; never collects or accepts it."""
    from portal.acme_lifecycle_read_model import project_synthetic_incident_lifecycle
    from portal.acme_evidence_collection_plan import plan_synthetic_evidence_collection
    try:
        plan = plan_synthetic_evidence_collection(
            project_synthetic_incident_lifecycle(_load_or_503())
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_evidence_plan_unqualified") from exc
    return JSONResponse(content=plan, headers=HEADERS)


@router.get("/api/demo/acme-itil-readiness", name="synthetic_acme_itil_readiness")
def acme_itil_readiness_json():
    """Expose missing evidence for ITIL transitions; never approve a transition."""
    from portal.acme_lifecycle_read_model import project_synthetic_incident_lifecycle
    from portal.acme_itil_readiness import assess_synthetic_itil_readiness
    try:
        lifecycle = project_synthetic_incident_lifecycle(_load_or_503())
        readiness = assess_synthetic_itil_readiness(lifecycle)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_itil_readiness_unqualified") from exc
    return JSONResponse(content=readiness, headers=HEADERS)


@router.get("/api/demo/acme-lifecycle", name="synthetic_acme_incident_itil_lifecycle")
def acme_lifecycle_json():
    """Read-only DEMO incident-to-ITIL lifecycle, no backend actions."""
    from portal.acme_lifecycle_read_model import project_synthetic_incident_lifecycle
    try:
        model = project_synthetic_incident_lifecycle(_load_or_503())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="synthetic_lifecycle_unqualified") from exc
    return JSONResponse(content=model, headers=HEADERS)


@router.get("/api/demo/acme-impact", name="synthetic_acme_impact_read_model")
def acme_impact_json():
    """Return the synthetic impact graph and explicit provenance gaps."""
    return JSONResponse(content=_load_or_503(), headers=HEADERS)


@router.get("/demo/acme-impact", response_class=HTMLResponse, name="synthetic_acme_impact_page")
def acme_impact_page():
    """Serve a local HTML snapshot; no scripts, forms or upstream calls."""
    model = _load_or_503()
    path = " → ".join(str(part) for part in model["impact_path"])
    rows = [
        ("Run ID (simulation)", model["run_id"], model["run_id_provenance"]),
        ("Incident source SAN P1", model["incident_id"], model["provenance"]),
        ("Incident d'impact Payments P2", model["impact_incident_id"], model["provenance"]),
        ("Ticket GLPI réel", "ABSENT", model["ticket_id_provenance"]),
        ("Horodatage runtime réel", "ABSENT", model["timestamp_provenance"]),
        ("Ticket de scénario (fictif)", model["simulation_ticket_id"], model["simulation_ticket_provenance"]),
        ("Horodatage de checkpoint (fictif)", model["simulation_checkpoint_timestamp_utc"], model["simulation_timestamp_provenance"]),
        ("Chemin d'impact calculé", path, "LOCAL_SYNTHETIC_DEPENDENCY_GRAPH"),
        ("Périmètre d'impact calculé", ", ".join(model["affected_ci_ids"]), "TRANSITIVE_DEPENDENCY_BLAST_RADIUS"),
        ("SHA-256 de la source", model["source_sha256"], "EXACT_FIXTURE_BYTES"),
        ("Source", model["source_artifact"], model["evidence_source"]),
        ("Qualification runtime", "NON", "runtime_attested=false"),
    ]
    ci_cards = "".join(
        '<article class="ci-card"><div class="ci-top"><strong>'
        + html.escape(str(ci["id"]), quote=True) + '</strong><span>'
        + html.escape(str(ci["impact_role"]).replace("_", " "), quote=True)
        + '</span></div><h3>' + html.escape(str(ci["name"]), quote=True)
        + '</h3><p>' + html.escape(str(ci["kind"]), quote=True)
        + '</p><small>Dépend de : '
        + html.escape(", ".join(ci["depends_on"]) if ci["depends_on"] else "Aucune dépendance")
        + '</small></article>'
        for ci in model["affected_cis"]
    )
    checkpoint_cards = "".join(
        '<article class="ci-card"><div class="ci-top"><strong>'
        + html.escape(str(item["cue"]).upper(), quote=True) + '</strong><span>MISSING</span></div>'
        + '<h3>' + html.escape(str(item["service"]).upper() + " · " + str(item["view"]), quote=True) + '</h3>'
        + '<p>État attendu : ' + html.escape(str(item["required_state"]), quote=True) + '</p>'
        + '<small>Capture : ABSENTE · SHA-256 : ABSENT · Horodatage runtime : ABSENT · Authentification : NON ATTESTÉE</small></article>'
        for item in model["checkpoint_evidence"]
    )
    decision = model["decision_preview"]
    decision_steps = "".join(
        "<li>" + html.escape(str(step), quote=True) + "</li>"
        for step in decision["remediation_preview"]
    )
    decision_checks = "".join(
        "<li>" + html.escape(str(step), quote=True) + "</li>"
        for step in decision["analyst"]["next_checks"]
    )
    table_rows = "".join(
        "<tr><th scope=\"row\">" + html.escape(str(label), quote=True)
        + "</th><td>" + html.escape(str(value), quote=True)
        + "</td><td>" + html.escape(str(provenance), quote=True) + "</td></tr>"
        for label, value, provenance in rows
    )
    path_nodes = "".join(
        "<g><rect x=\"" + str(25 + i * 230) + "\" y=\"72\" width=\"190\" height=\"76\" rx=\"12\" "
        "fill=\"" + ("#7f1d1d" if i == 0 else "#172136" if i < len(model["impact_path"]) - 1 else "#7c2d12") + "\" "
        "stroke=\"#cbd5e1\" stroke-width=\"2\"/>"
        "<text x=\"" + str(120 + i * 230) + "\" y=\"101\" text-anchor=\"middle\" "
        "font-family=\"Arial,sans-serif\" font-size=\"16\" fill=\"#ffffff\">"
        + html.escape(str(node), quote=True) + "</text>"
        "<text x=\"" + str(120 + i * 230) + "\" y=\"124\" text-anchor=\"middle\" "
        "font-family=\"Arial,sans-serif\" font-size=\"14\" fill=\"#e2e8f0\">"
        + ("SAN P1" if i == 0 else "SERVICE IMPACT" if i == len(model["impact_path"]) - 1 else "DEPENDENCY") + "</text></g>"
        for i, node in enumerate(model["impact_path"])
    )
    arrows = "".join(
        "<path d=\"M " + str(215 + i * 230) + " 110 h 30\" stroke=\"#8b5cf6\" "
        "stroke-width=\"3\" fill=\"none\"/><path d=\"M " + str(237 + i * 230) + " 103 l 8 7 -8 7\" "
        "stroke=\"#8b5cf6\" stroke-width=\"3\" fill=\"none\"/>"
        for i in range(max(0, len(model["impact_path"]) - 1))
    )
    diagram = (
        "<section aria-label=\"Graphe de dépendances illustratif\">"
        "<h2>Chemin d'impact calculé</h2>"
        "<p>Graphe local construit depuis le fixture synthétique ; pas une topologie runtime.</p>"
        "<svg xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"Dépendances SAN vers application Payments, simulation\" "
        "viewBox=\"0 0 980 180\" width=\"100%\" height=\"180\" preserveAspectRatio=\"xMinYMin meet\">"
        "<rect width=\"980\" height=\"180\" rx=\"14\" fill=\"#111827\"/>"
        + arrows + path_nodes + "</svg><ol class=\"mobile-path\">" + "".join("<li>" + html.escape(str(node)) + "</li>" for node in model["impact_path"]) + "</ol></section>"
    )
    body = (
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>ACME — impact SAN P1 vers Payments P2 (simulation)</title>"
        "<style>body{margin:0;background:#0b1220;color:#eef5ff;font:15px/1.55 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:clamp(16px,4vw,44px)}h1{font-size:clamp(2rem,4vw,3.2rem)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:24px 0}.kpi{background:#121e31;border:1px solid #334155;border-radius:14px;padding:16px}.kpi span{display:block;color:#b8c7df;font-size:.82rem}.kpi strong{display:block;font-size:1.25rem;margin-top:4px}.kpi .p1{color:#ff6878}.kpi .p2{color:#ffc66d}.ci-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:18px 0}.ci-card{background:#121e31;border:1px solid #334155;border-radius:12px;padding:14px;min-width:0}.ci-top{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap}.ci-top strong{color:#38bdf8}.ci-top span{font-size:.7rem;color:#ffc66d}.ci-card h3{font-size:1rem;margin:10px 0 2px;overflow-wrap:anywhere}.ci-card p{color:#b8c7df;margin:0 0 10px}.ci-card small{color:#b8c7df;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;background:#121e31;border-radius:12px;overflow:hidden}th,td{text-align:left;padding:12px;border-bottom:1px solid #334155;overflow-wrap:anywhere}th{color:#38bdf8}td:nth-child(3){color:#b8c7df;font-size:.85rem}svg{max-width:100%;height:auto}caption{text-align:left;padding:12px;color:#38bdf8;font-weight:700}@media(max-width:600px){main{padding:14px}th,td{padding:7px;font-size:.78rem}}body{background:#080b14;color:#f4f7ff}.kpi,.ci-card,table{background:#111827}.table-scroll{overflow-x:auto;max-width:100%}.table-scroll table{min-width:620px}th,td{font-size:.9rem;overflow-wrap:normal;word-break:normal}td:nth-child(3){font-size:.9rem}td{overflow-wrap:normal}.table-scroll td:nth-child(2){min-width:200px;overflow-wrap:anywhere;font-family:ui-monospace,monospace}.table-scroll td:nth-child(3){min-width:190px;overflow-wrap:anywhere}.table-scroll:focus-visible{outline:3px solid #38bdf8;outline-offset:3px}a{color:#38bdf8}a:focus-visible{outline:3px solid #38bdf8;outline-offset:3px}header a{display:inline-block;padding:.4rem 0}.mobile-path{display:none}@media(max-width:1100px){svg{display:none}.mobile-path{display:block}.mobile-path li{padding:.7rem;background:#172136;margin:.4rem 0;overflow-wrap:anywhere}}</style>"
        "</head><body><main><header><a href=\"/#incidents\">Retour Incident Explorer</a></header><h1>ACME — SAN P1 → Payments P2</h1>"
        "<p><strong>SIMULATION LOCALE UNIQUEMENT.</strong> Aucun incident runtime, "
        "ticket GLPI, capture applicative, appel backend ou événement horodaté n'est créé. "
        "Le run_id affiché est dérivé des octets du fixture, pas d'un run exécuté.</p>"
        + "<p><strong>GO — scénario synthétique · UNKNOWN — preuves runtime · NO-GO LIVE</strong></p>" + diagram +
        '<section class="kpis" aria-label="Indicateurs du scénario">'
        '<article class="kpi"><span>Incident source</span><strong class="p1">SAN P1</strong><span>Dégradation de fabric simulée</span></article>'
        '<article class="kpi"><span>Service impacté</span><strong class="p2">Payments P2</strong><span>Impact métier simulé</span></article>'
        '<article class="kpi"><span>Éléments de configuration</span><strong>' + str(model["ci_count"]) + '</strong><span>Dans le fixture local</span></article>'
        '<article class="kpi"><span>Incidents du scénario</span><strong>' + str(model["incident_count"]) + '</strong><span>Jeu de données local</span></article>'
        '</section>'
        '<section aria-label="Inventaire des CI affectées"><h2>Inventaire d’impact détaillé</h2>'
        '<p>Chaque carte est issue du graphe de dépendances du scénario ; les dépendances affichées sont déclaratives et synthétiques.</p>'
        '<div class="ci-grid">' + ci_cards + '</div></section>'
        + '<section aria-label="Décision et remédiation en simulation"><h2>Analyst · Critic · Policy — prévisualisation</h2>'
        + '<p><strong>Fournisseur :</strong> ' + html.escape(decision["provider"], quote=True) + '</p>'
        + '<p><strong>Analyst :</strong> ' + html.escape(decision["analyst"]["status"], quote=True) + ' — ' + html.escape(decision["analyst"]["summary"], quote=True) + '</p>'
        + '<ul>' + decision_checks + '</ul>'
        + '<p><strong>Critic :</strong> ' + html.escape(decision["critic"]["decision"], quote=True) + ' — ' + html.escape(decision["critic"]["reason"], quote=True) + '</p>'
        + '<p><strong>Policy :</strong> ' + html.escape(decision["policy"]["decision"], quote=True) + ' — ' + html.escape(decision["policy"]["reason"], quote=True) + '</p>'
        + '<h3>Plan de remédiation proposé (sans exécution)</h3><ol>' + decision_steps + '</ol>'
        + '<p><strong>Exécution LIVE :</strong> NON · <strong>Écritures backend :</strong> NON</p></section>'
        + '<section aria-label="Neuf checkpoints applicatifs attendus"><h2>STAR — checkpoints applicatifs et preuves manquantes</h2>'
        + '<p>Les noms de vues et états sont le contrat attendu, pas des captures observées. Les URL runtime exactes, les identifiants applicatifs et les SHA-256 de captures ne sont pas disponibles dans ce scénario.</p>'
        + '<div class="ci-grid">' + checkpoint_cards + '</div></section>'
        + "<p>Tableau : défilement horizontal si nécessaire, avec les flèches après Tab.</p><div class=\"table-scroll\" role=\"region\" aria-label=\"Provenance\" tabindex=\"0\"><table><caption>Identifiants, provenance et trous de preuve</caption>"
        "<thead><tr><th scope=\"col\">Champ</th><th scope=\"col\">Valeur</th>"
        "<th scope=\"col\">Origine / qualification</th></tr></thead>"
        "<tbody>" + table_rows + "</tbody></table></div>"
        "<p>Remédiation LIVE autorisée : NON. Les identifiants et l'horloge de scénario sont "
        "déterministes et fictifs ; aucun ticket GLPI ni événement runtime n'existe.</p>"
        "</main></body></html>"
    )
    return HTMLResponse(content=body, headers=HEADERS)
