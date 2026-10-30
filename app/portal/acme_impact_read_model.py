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
                "itil_practice": practice,
                "owner_role": owner_role,
                "handoff": handoff,
                "evidence_required": evidence_required,
                "status": "MISSING",
                "screenshot_sha256": None,
                "event_timestamp_utc": None,
                "runtime_authenticated": False,
                "source": "SYNTHETIC_ITIL_CHECKPOINT_CONTRACT_ONLY_NO_CAPTURE",
            }
            for cue, service, view, required_state, practice, owner_role, handoff, evidence_required in (
                ("detect", "prometheus", "source_alert", "firing", "monitoring_event_management", "noc_l1", "monitoring_to_noc_l1", "source_event_id_observed_at_dedupe_key"),
                ("correlate", "twin", "service_dependency_path", "source_backed", "service_configuration_management", "noc_l2", "noc_l1_to_noc_l2", "ci_service_edge_source_and_freshness"),
                ("acknowledge", "service_desk", "incident_intake", "acknowledged", "incident_management", "service_desk_n1", "noc_l1_to_service_desk_n1", "actor_timestamp_assignment_and_sla_start"),
                ("assess_impact", "core", "impact_urgency_priority", "assessed", "incident_management", "incident_manager_n2", "n1_to_incident_manager_n2", "impact_urgency_policy_version_and_rationale"),
                ("declare_major", "major_incident", "command_and_communications", "declared", "incident_management", "incident_commander", "n2_to_incident_commander", "commander_assignment_and_customer_update"),
                ("collect_evidence", "evidence", "evidence_bundle", "collected", "monitoring_event_management", "sre_n3", "incident_commander_to_sre_n3", "evidence_id_hash_source_observed_at_known_at"),
                ("retrieve_knowledge", "rag", "runbook_and_known_error", "retrieved", "knowledge_management", "knowledge_manager", "sre_n3_to_knowledge_manager", "document_version_acl_owner_and_citations"),
                ("analyze_root_cause", "analyst_critic", "hypothesis_and_challenge", "reviewed", "problem_management", "problem_manager_n3", "knowledge_manager_to_problem_manager_n3", "hypothesis_evidence_contradictions_and_critic_disposition"),
                ("propose_change", "policy", "risk_and_rollback_plan", "proposed", "change_enablement", "change_manager", "problem_manager_to_change_manager", "risk_scope_preconditions_postconditions_and_rollback"),
                ("approve_change", "hitl", "human_decision", "approved_simulation_only", "change_enablement", "authorized_approver", "change_manager_to_authorized_approver", "verified_identity_role_scope_nonce_expiry_and_proposal_hash"),
                ("simulate_action", "temporal", "sandbox_simulation", "simulated_no_effect", "deployment_management", "automation_operator", "approver_to_automation_operator", "simulation_receipt_execution_allowed_false"),
                ("verify_recovery", "verification", "service_health_and_slo", "verified", "service_validation_testing", "independent_verifier", "automation_operator_to_independent_verifier", "independent_postcondition_evidence_and_before_after"),
                ("close_incident", "service_desk", "incident_closure", "resolved", "incident_management", "service_desk_n1", "independent_verifier_to_service_desk_n1", "resolution_code_customer_confirmation_and_timeline"),
                ("problem_review", "continual_improvement", "pir_known_error_and_actions", "reviewed", "continual_improvement", "service_owner", "service_desk_to_service_owner", "verified_cause_action_owner_due_date_and_knowledge_review"),
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
        "fill=\"" + ("#7f1d1d" if i == 0 else "#17365d" if i < len(model["impact_path"]) - 1 else "#7c2d12") + "\" "
        "stroke=\"#cbd5e1\" stroke-width=\"2\"/>"
        "<text x=\"" + str(120 + i * 230) + "\" y=\"101\" text-anchor=\"middle\" "
        "font-family=\"Arial,sans-serif\" font-size=\"13\" fill=\"#ffffff\">"
        + html.escape(str(node), quote=True) + "</text>"
        "<text x=\"" + str(120 + i * 230) + "\" y=\"124\" text-anchor=\"middle\" "
        "font-family=\"Arial,sans-serif\" font-size=\"10\" fill=\"#e2e8f0\">"
        + ("SAN P1" if i == 0 else "SERVICE IMPACT" if i == len(model["impact_path"]) - 1 else "DEPENDENCY") + "</text></g>"
        for i, node in enumerate(model["impact_path"])
    )
    arrows = "".join(
        "<path d=\"M " + str(215 + i * 230) + " 110 h 30\" stroke=\"#64748b\" "
        "stroke-width=\"3\" fill=\"none\"/><path d=\"M " + str(237 + i * 230) + " 103 l 8 7 -8 7\" "
        "stroke=\"#64748b\" stroke-width=\"3\" fill=\"none\"/>"
        for i in range(max(0, len(model["impact_path"]) - 1))
    )
    diagram = (
        "<section aria-label=\"Graphe de dépendances illustratif\">"
        "<h2>Chemin d'impact calculé</h2>"
        "<p>Graphe local construit depuis le fixture synthétique ; pas une topologie runtime.</p>"
        "<svg xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"Dépendances SAN vers application Payments, simulation\" "
        "viewBox=\"0 0 980 180\" width=\"100%\" height=\"180\" preserveAspectRatio=\"xMinYMin meet\">"
        "<rect width=\"980\" height=\"180\" rx=\"14\" fill=\"#f8fafc\"/>"
        + arrows + path_nodes + "</svg></section>"
    )
    body = (
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>ACME — impact SAN P1 vers Payments P2 (simulation)</title>"
        "<style>body{margin:0;background:#0b1220;color:#eef5ff;font:15px/1.55 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:clamp(16px,4vw,44px)}h1{font-size:clamp(2rem,4vw,3.2rem)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:24px 0}.kpi{background:#121e31;border:1px solid #2a3b55;border-radius:14px;padding:16px}.kpi span{display:block;color:#a8b8ce;font-size:.82rem}.kpi strong{display:block;font-size:1.25rem;margin-top:4px}.kpi .p1{color:#ff6878}.kpi .p2{color:#ffc66d}.ci-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:18px 0}.ci-card{background:#121e31;border:1px solid #2a3b55;border-radius:12px;padding:14px;min-width:0}.ci-top{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap}.ci-top strong{color:#65d9ee}.ci-top span{font-size:.7rem;color:#ffc66d}.ci-card h3{font-size:1rem;margin:10px 0 2px;overflow-wrap:anywhere}.ci-card p{color:#a8b8ce;margin:0 0 10px}.ci-card small{color:#a8b8ce;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;background:#121e31;border-radius:12px;overflow:hidden}th,td{text-align:left;padding:12px;border-bottom:1px solid #2a3b55;overflow-wrap:anywhere}th{color:#65d9ee}td:nth-child(3){color:#a8b8ce;font-size:.85rem}svg{max-width:100%;height:auto}caption{text-align:left;padding:12px;color:#65d9ee;font-weight:700}@media(max-width:600px){main{padding:14px}th,td{padding:7px;font-size:.78rem}}</style>"
        "</head><body><main><h1>ACME — SAN P1 → Payments P2</h1>"
        "<p><strong>SIMULATION LOCALE UNIQUEMENT.</strong> Aucun incident runtime, "
        "ticket GLPI, capture applicative, appel backend ou événement horodaté n'est créé. "
        "Le run_id affiché est dérivé des octets du fixture, pas d'un run exécuté.</p>"
        + diagram +
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
        + "<table><caption>Identifiants, provenance et trous de preuve</caption>"
        "<thead><tr><th scope=\"col\">Champ</th><th scope=\"col\">Valeur</th>"
        "<th scope=\"col\">Origine / qualification</th></tr></thead>"
        "<tbody>" + table_rows + "</tbody></table>"
        "<p>Remédiation LIVE autorisée : NON. Les identifiants et l'horloge de scénario sont "
        "déterministes et fictifs ; aucun ticket GLPI ni événement runtime n'existe.</p>"
        "</main></body></html>"
    )
    return HTMLResponse(content=body, headers=HEADERS)
