"""Isolated read-only AIOps demo viewer. DEMO data, never operational controls."""
import html
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

CORE = os.getenv("CORE_URL", "http://aiops2-core:810").rstrip("/")
TOKEN = os.environ["AIOPS_INTERNAL_TOKEN"]
ALLOW = {
    "RUN-D885843CC98AAC53",
    "RUN-46E80E7EFB278E93",
    "RUN-900218229559A6A3",
}

def fetch(path):
    req = urllib.request.Request(CORE + path, headers={
        "Authorization": "Bearer " + TOKEN,
        "X-AIOPS-Request": "internal",
    })
    with urllib.request.urlopen(req, timeout=6) as response:
        return json.load(response)

def esc(s):
    return html.escape(str(s), quote=True)

def panel(title, value):
    return '<section class="panel"><h2>' + esc(title) + '</h2>' + value + '</section>'

def table(rows, headers):
    return '<table><thead><tr>' + ''.join('<th>'+esc(k)+'</th>' for k in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows) + '</tbody></table>'

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path not in ("/", "/health"):
            self.send_error(404)
            return
        if parsed.path == "/health":
            content=b'{"status":"ok","readonly":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        try:
            run_id = parse_qs(parsed.query).get("run", ["RUN-D885843CC98AAC53"])[0]
            if run_id not in ALLOW:
                self.send_error(404)
                return
            runs = fetch("/api/runs")
            detail = fetch("/api/runs/" + run_id)
            ledger = fetch("/api/runs/" + run_id + "/ai-ledger")
            dashboard = fetch("/api/dashboard")
            entries = [x for x in runs.get("items", []) if x.get("run_id") in ALLOW]
            choices = ''.join('<a href="/?run='+esc(x['run_id'])+'">'+esc(x['run_id'])+'</a>' for x in entries)
            events = detail.get("events", [])
            events_table = table([(e.get("sequence",""),e.get("stage",""),e.get("event_type",""),e.get("status","")) for e in events],["#","Étape","Événement","État"])
            ai_panels = ''
            for name in ("analyses", "critiques", "policy_decisions"):
                items = ledger.get(name, [])
                ai_panels += panel(name + " (" + str(len(items)) + ")", "<pre>"+esc(json.dumps(items, ensure_ascii=False, indent=2, default=str))+"</pre>")
            body = '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="20"><title>AIOps 2.0 — Démonstration</title><style>body{font:15px system-ui;background:#0a1826;color:#e9f4ff;margin:0}main{max-width:1450px;margin:auto;padding:26px}header{background:#10283b;padding:18px 26px;border-bottom:1px solid #34536b}.sub{color:#a2bbc9}h1{margin:0}h2{margin-top:0;font-size:19px}.panel{background:#102638;border:1px solid #375267;border-radius:12px;padding:18px;margin:15px 0;overflow:auto}a{display:inline-block;padding:9px 13px;color:#a7dcff;margin:8px 8px 0 0;border:1px solid #34536b;border-radius:6px;text-decoration:none}table{border-collapse:collapse;width:100%}th,td{padding:9px;border-bottom:1px solid #294357;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}strong{color:#88dcad}</style></head><body><header><h1>AIOps 2.0 — DEMO isolée</h1><div class="sub">Lecture seule · preuves synthétiques qualifiées · aucune action LIVE</div></header><main>'
            body += panel("Campagnes disponibles", choices)
            body += panel("Run sélectionné", "<strong>"+esc(run_id)+"</strong> — "+esc(detail["run"].get("status", "UNKNOWN"))+"<p>Tableau de bord : "+esc(json.dumps(dashboard, ensure_ascii=False, default=str))+"</p>")
            body += panel("Chronologie des étapes", events_table)
            body += ai_panels
            body += '<p class="sub">Statut métier BLOCKED distinct du statut technique Temporal COMPLETED. Rafraîchissement automatique toutes les 20 secondes.</p></main></body></html>'
            content=body.encode("utf-8")
        except Exception as exc:
            self.log_error("read-only backend failure %s", type(exc).__name__)
            content=b'<h1>DEMO indisponible</h1><p>Consulter les preuves Temporal de secours.</p>'
            self.send_response(503)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'")
        self.send_header("Content-Length",str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        self.send_error(405, "Read-only DEMO")

ThreadingHTTPServer(("0.0.0.0", 777), Handler).serve_forever()
