"""Accessible offline scene navigator for verified STAR transport exports.

Generates pure HTML with fragment navigation only: no JS, network, external URLs,
production endpoints, remediation controls, images or arbitrary markup injection.
"""
from __future__ import annotations
import html
from collections.abc import Mapping
from demo.star_scene_scripts import scene_plan

def render_navigator(transport: Mapping[str, object], scenario: str) -> str:
    plan = scene_plan(scenario, transport)
    steps = plan["steps"]
    nav = []
    articles = []
    for index, step in enumerate(steps, 1):
        ident = "scene-" + str(index)
        title = step["step"].replace("_", " ").title()
        application = html.escape(step["application"].upper(), quote=True)
        view = html.escape(step["view"].replace("_", " "), quote=True)
        narration = html.escape(step["narration"], quote=True)
        status = {
            "missing": "Capture absente — aucune preuve visuelle",
            "simulated": "Illustration fictive — pas une preuve runtime",
            "integrity_checked": "Intégrité PNG contrôlée — origine runtime non authentifiée",
        }[step["capture_status"]]
        nav.append(f'<a href="#{ident}" aria-label="Afficher étape {index}">{index:02d} {html.escape(title)}</a>')
        articles.append(
            f'<section id="{ident}" tabindex="-1" aria-labelledby="title-{index}">'
            f'<p class="counter">ÉTAPE {index:02d} / 09 · {application}</p>'
            f'<h2 id="title-{index}">{html.escape(title)}</h2>'
            f'<p class="story">{narration}</p><p>Vue attendue : <strong>{view}</strong></p>'
            f'<p class="evidence">{html.escape(status)}</p>'
            '<p class="limitations">Aucune action LIVE. L’état métier doit être prouvé séparément.</p>'
            '</section>'
        )
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
<title>AIOps STAR — scénario hors ligne</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#081627;color:#eef5ff}
body{max-width:1180px;margin:auto;padding:2rem}nav{display:flex;gap:.5rem;flex-wrap:wrap}
nav a{color:#d4edff;background:#1d3956;border-radius:.5rem;padding:.6rem;text-decoration:none}
nav a:focus-visible{outline:3px solid #fbd47b}
section{border:1px solid #476683;padding:2rem;margin:1rem 0;border-radius:1rem;background:#112b43}
section:target{border:3px solid #fbd47b}h1{font-size:clamp(1.5rem,4vw,2.8rem)}
.counter{color:#8cc9ec;font-weight:bold}.story{font-size:1.2rem}
.evidence{padding:1rem;border-left:4px solid #fbd47b;background:#213c54}
.limitations{color:#a9c4d8}.notice{color:#fbd47b}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style></head><body><main><h1>""" + html.escape(plan["title"]) + """</h1>
<p class="notice">Démonstration synthétique — navigation locale, pas de preuve runtime ni action de production.</p>
<nav aria-label="Navigation des neuf étapes">""" + "".join(nav) + """</nav>""" + "".join(articles) + """</main></body></html>"""

