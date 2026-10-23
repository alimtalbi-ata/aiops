"""Static, read-only HTML storyboard renderer; no live endpoints or JS.

Only sanitized enum-derived fields are shown; no image URL, source URL,
credentials, incident payload, or arbitrary metadata is embedded.
"""
from __future__ import annotations
import html
from collections.abc import Mapping
from demo.star_snapshot_choreography import CUES
from demo.star_portal_storyboard import storyboard

_TITLES = {
    "detect": "Détection", "correlate": "Corrélation",
    "enrich": "Contexte & CMDB", "analyze": "Analyse & critique IA",
    "ticket": "Ticket GLPI", "approve": "Validation humaine",
    "simulate": "Remédiation simulée", "verify": "Vérification",
    "close": "Clôture et apprentissage",
}

def render_storyboard(report: Mapping[str, object], scenario: str) -> str:
    view = storyboard(report, scenario)
    cards = []
    for number, frame in enumerate(view["frames"], 1):
        # All text comes from canonical cue definitions or strict renderer enums.
        title = _TITLES[frame["step"]]
        label = html.escape(frame["caption"], quote=True)
        service = html.escape(frame["application"].upper(), quote=True)
        expected = html.escape(frame["expected_state"].replace("_", " "), quote=True)
        cards.append(
            f'<li class="frame" aria-label="Étape {number}: {html.escape(title)}">'
            f'<span class="count">{number:02d}</span>'
            f'<div><h2>{html.escape(title)}</h2>'
            f'<p class="service">{service} · état attendu : {expected}</p>'
            f'<p class="status">{label}</p></div></li>'
        )
    scenario_title = "SAN Fabric P1" if scenario == "SAN_FABRIC_P1" else "Payments P2"
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
<title>AIOps STAR — consultation seule</title>
<style>
:root{color-scheme:dark;font:16px system-ui,Arial,sans-serif;background:#081628;color:#f4f7fd}
body{margin:0 auto;max-width:1100px;padding:2rem}
h1{font-size:clamp(1.8rem,4vw,3rem);margin:.5rem 0}
strong{color:#f7c766}.sub{color:#a9c1d8}
ol{padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(265px,1fr));gap:1rem;list-style:none}
.frame{display:flex;gap:1rem;padding:1.2rem;border:1px solid #37516d;border-radius:14px;background:#14283e}
.count{font-weight:800;font-size:1.4rem;color:#80c5f6}h2{font-size:1.1rem;margin:0 0 .6rem}
.service{color:#b9cddf;font-size:.9rem}.status{font-weight:700;color:#f8cc78}
.notice{border-left:4px solid #f7c766;padding:.8rem 1rem;background:#1b3046}
footer{color:#a9c1d8;margin:2rem 0}
</style></head><body><main><p class="sub">AIOps 2.0 · STAR · mode démonstration</p>
<h1>""" + html.escape(scenario_title) + """</h1>
<p class="notice"><strong>Simulation / qualification documentaire :</strong>
aucune capture ne prouve seule un événement runtime. Aucun bouton de remédiation,
aucune écriture GLPI, aucune commande n8n.</p>
<ol>""" + "".join(cards) + """</ol>
<footer>Présentation statique, sans scripts, appels réseau ni autorisation LIVE.</footer>
</main></body></html>"""
