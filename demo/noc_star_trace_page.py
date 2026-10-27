"""Render synthetic STAR event hashes beside reviewed OFFLINE_TEST NOC captures."""
from __future__ import annotations
import html
from demo.noc_star_event_binding import bind_synthetic_star_events

def render_noc_star_trace(index:dict, events:list)->str:
    trace=bind_synthetic_star_events(index,events)
    esc=lambda value:html.escape(str(value),quote=True)
    rows="".join('<tr id="cue-'+esc(item["cue"])+'"><td>'+esc(item["cue"])+"</td><td>"+esc(item["event_id"])+"</td><td><code>"+esc(item["event_sha256"])+"</code></td></tr>" for item in trace["events"])
    captures="".join("<tr><td>"+esc(item["file"])+"</td><td>"+", ".join('<a href="#cue-'+esc(cue)+'">'+esc(cue)+"</a>" for cue in item["illustrative_cues"])+"</td><td>"+esc(item["relationship"])+"</td></tr>" for item in trace["captures"])
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>STAR · preuves illustratives</title>
<style>:root{color-scheme:dark;background:#08192a;color:#eef7ff;font:15px system-ui}body{padding:20px;max-width:1200px;margin:auto}
section{background:#163148;padding:16px;margin:16px 0;border-radius:10px}
table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #3a5368}
code{overflow-wrap:anywhere}</style></head><body>
<h1>AIOps — Chronologie STAR simulée</h1><p>OFFLINE_TEST · événements SYNTHETIC · association de captures ILLUSTRATIVE_ONLY · zéro preuve runtime</p>
<section><h2>Identité de démonstration</h2><p>Run : """+esc(trace["run_id"])+""" · Incident : """+esc(trace["incident_id"])+"""</p></section>
<section><h2>Neuf événements</h2><table><thead><tr><th>Étape</th><th>Événement</th><th>SHA-256 événement</th></tr></thead><tbody>"""+rows+"""</tbody></table></section>
<section><h2>Captures illustratives</h2><table><thead><tr><th>Fichier</th><th>Étapes</th><th>Relation</th></tr></thead><tbody>"""+captures+"""</tbody></table></section></body></html>"""
