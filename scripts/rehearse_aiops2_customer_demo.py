"""Generate a customer-facing, read-only rehearsal sheet from a verified demo package."""
import argparse
import json
import sys
from pathlib import Path

from package_aiops2_demo_evidence import verify_package

def build_rehearsal(directory):
    directory = Path(directory)
    if not verify_package(directory):
        raise ValueError("noncanonical_demo_package")
    cockpit = json.loads((directory / "cockpit.json").read_text("utf-8"))
    report = json.loads((directory / "acceptance.json").read_text("utf-8"))
    if (report.get("accepted") is not True
            or cockpit.get("runtime_attested") is not False
            or cockpit.get("live_remediation_authorized") is not False
            or cockpit.get("overall_qualification") != "UNKNOWN"
            or cockpit["itil_readiness"]["authorized_transition_count"] != 0
            or cockpit["evidence_plan"]["verified_count"] != 0
            or cockpit["analyst_critic_review"]["runtime_citations_verified"] != 0
            or cockpit["analyst_critic_review"]["policy_disposition"] != "DENY_LIVE_ACTION"):
        raise ValueError("unsafe_rehearsal_state")
    stages = cockpit["lifecycle"]["stages"]
    transitions = cockpit["itil_readiness"]["transitions"]
    if (len(stages) != 9 or len(transitions) != 8
            or any(stage["evidence_state"] != "UNKNOWN"
                   or stage["runtime_attested"] is not False
                   or stage["operational_transition_authorized"] is not False
                   for stage in stages)
            or any(gate["readiness"] != "UNKNOWN"
                   or gate["authorized"] is not False for gate in transitions)):
        raise ValueError("unsafe_rehearsal_checkpoints")
    lines = [
        "# Répétition opérateur — ACME P1 SAN → Payments",
        "",
        "**DEMO SYNTHÉTIQUE — NO-GO LIVE — aucune attestation runtime.**",
        "",
        f"- Incident technique : `{cockpit['incident_id']}`",
        f"- Impact métier : `{cockpit['business_impact_incident_id']}`",
        f"- Fixture SHA-256 : `{cockpit['source_sha256']}`",
        "- Parcours de dépendances : " + " → ".join(
            str(x) for x in cockpit["business_impact_path"]),
        "",
        "| Minute | Montrer à l'opérateur | Critère observable |",
        "|---|---|---|",
        "| 00–02 | Incident P1 et dépendance Payments | IDs et SHA identiques |",
        "| 02–04 | Plan de collecte | 0 preuve runtime vérifiée |",
        "| 04–06 | Analyst/Critic | Hypothèse uniquement, 0 citation runtime |",
        "| 06–08 | Policy/HITL | DENY_LIVE_ACTION, 0 transition autorisée |",
        "| 08–10 | Simulation et postcheck | Aucun effet réel, postcheck UNKNOWN |",
        "| 10–12 | Préparation ITIL | Collecter les preuves indépendantes, aucune clôture GLPI |",
        "",
        "## Matrice des preuves manquantes (9 étapes)",
        "",
        "| Étape | Source attendue | État |",
        "|---|---|---|",
        *[
            f"| \`{stage['cue']}\` | \`{stage['expected_source']}\` | UNKNOWN — preuve indépendante absente |"
            for stage in stages
        ],
        "",
        "## Transitions ITIL bloquées (8 contrôles)",
        "",
        "| Transition | Prérequis manquants | Autorisation |",
        "|---|---|---|",
        *[
            f"| \`{gate['transition']}\` | {', '.join(gate['missing_evidence'])} | NON — UNKNOWN |"
            for gate in transitions
        ],
        "",
        "## Décision de sortie",
        "",
        "- **GO** : présentation du scénario synthétique et de ses limites.",
        "- **NO-GO** : action LIVE, récupération réelle, clôture ITIL, validation d'un humain.",
        "- **UNKNOWN** : attestation runtime, preuves externes, diagnostic IA réel.",
        "",
        "Ne jamais convertir une projection de fixture en preuve d'exécution.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        document = build_rehearsal(args.package)
        if args.output:
            args.output.write_text(document, encoding="utf-8")
        else:
            print(document)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
