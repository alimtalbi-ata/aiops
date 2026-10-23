"""STAR scene narration with application-specific screenshot cues.

Synthetic demo script only. It never claims runtime events occurred.
"""
from __future__ import annotations

from collections.abc import Mapping
from demo.star_snapshot_choreography import CUES

SCENARIOS = {
    "SAN_FABRIC_P1": {
        "title": "Perte de redondance SAN — incident P1",
        "hypothesis": "Perte d'un chemin FC ; impact potentiel des volumes Payments",
        "priority": "P1",
        "scenes": {
            "detect": "Observer les alertes FC et multipath dans Grafana.",
            "correlate": "Identifier les événements rapprochés dans l'exécution n8n Ingress.",
            "enrich": "Afficher CMDB, dépendances applicatives et identité de Run.",
            "analyze": "Présenter diagnostic DGX et objections du Critic.",
            "ticket": "Vérifier le ticket GLPI correspondant au Run.",
            "approve": "Exposer la décision HITL ; ne jamais l'effectuer en production.",
            "simulate": "Afficher exclusivement une exécution de remédiation simulée.",
            "verify": "Comparer les mesures avant/après, sans inventer de rétablissement.",
            "close": "Consulter résolution et apprentissage si preuves disponibles.",
        },
    },
    "PAYMENTS_P2": {
        "title": "Dégradation Payments — incident P2",
        "hypothesis": "Latence applicative ; origine stockage ou applicative à départager",
        "priority": "P2",
        "scenes": {
            "detect": "Observer latence et erreurs Payments dans Grafana.",
            "correlate": "Comparer incidents connexes et fenêtre temporelle dans n8n.",
            "enrich": "Consulter contexte, métriques et dépendances de Payments.",
            "analyze": "Comparer hypothèses de cause et contre-analyse Critic.",
            "ticket": "Inspecter le ticket GLPI et son impact métier.",
            "approve": "Présenter le gate décisionnel et l'absence d'autorisation LIVE.",
            "simulate": "Montrer uniquement le scénario de simulation isolée.",
            "verify": "Comparer SLO avant/après sans supposer un retour à la normale.",
            "close": "Présenter les conditions de clôture et observations disponibles.",
        },
    },
}

def scene_plan(scenario: str, storyboard: Mapping[str, object]) -> dict:
    if scenario not in SCENARIOS:
        raise ValueError("unknown STAR scenario")
    if storyboard.get("schema") != "star-portal-transport-v1":
        raise ValueError("invalid storyboard schema")
    if storyboard.get("scenario") != scenario:
        raise ValueError("scenario mismatch")
    safety = storyboard.get("safety")
    if not isinstance(safety, dict) or safety.get("read_only") is not True:
        raise ValueError("unsafe storyboard")
    if safety.get("remediation_authorized") is not False or safety.get("runtime_authenticated") is not False:
        raise ValueError("unauthorized runtime claim")
    frames = storyboard.get("frames")
    if not isinstance(frames, list) or len(frames) != len(CUES):
        raise ValueError("wrong scene count")
    definition = SCENARIOS[scenario]
    steps = []
    for cue, frame in zip(CUES, frames):
        if not isinstance(frame, dict) or frame.get("step") != cue.cue:
            raise ValueError("out-of-order STAR scene")
        if frame.get("application") != cue.service or frame.get("expected_view") != cue.view:
            raise ValueError("wrong application or view for cue")
        if frame.get("action_allowed") is not False or frame.get("runtime_verified") is not False:
            raise ValueError("unexpected action or proof claim")
        capture_status = frame.get("capture_status")
        if capture_status not in {"missing", "simulated", "integrity_checked"}:
            raise ValueError("invalid evidence status")
        steps.append({
            "step": cue.cue,
            "application": cue.service,
            "view": cue.view,
            "narration": definition["scenes"][cue.cue],
            "capture_status": capture_status,
            "verified_runtime": False,
            "action_allowed": False,
        })
    return {
        "schema": "star-demo-scene-plan-v1",
        "scenario": scenario,
        "title": definition["title"],
        "hypothesis": definition["hypothesis"],
        "priority": definition["priority"],
        "synthetic_scenario": True,
        "steps": steps,
        "runtime_qualified": False,
        "live_action_authorized": False,
    }
