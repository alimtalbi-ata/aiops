"""Shared presentation shell for AIOps portals.

Reference: user-supplied 'Timeline AIOps : de l'incident à la remédiation'.
The styling is adapted, not a claim that the reference's fictional metrics occurred.
"""
import html
import json

THEME = """
:root{--bg:#f3f2ee;--card:#fff;--text:#1d1d1b;--muted:#64635d;--line:#dedcd3;--hero:#14122b;--c:#7F77DD}
:root[data-theme="dark"]{--bg:#101014;--card:#1b1b21;--text:#f2f1ec;--muted:#a5a49c;--line:#34343c}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#101014;--card:#1b1b21;--text:#f2f1ec;--muted:#a5a49c;--line:#34343c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:inherit}a:focus-visible,button:focus-visible,textarea:focus-visible{outline:3px solid #EF9F27;outline-offset:3px}
.hero{color:#fff;text-align:center;background:radial-gradient(ellipse at 20% 10%,#514383 0,transparent 42%),radial-gradient(ellipse at 85% 85%,#155748 0,transparent 38%),#14122b;padding:35px 18px 50px}
.hero h1{font-size:clamp(1.5rem,4vw,2.4rem);margin:0 0 8px}
.hero h1 span{background:linear-gradient(90deg,#F09595,#FAC775,#9FE1CB,#85B7EB);background-clip:text;color:transparent}
.hero p{opacity:.83;max-width:760px;margin:0 auto 12px}
.pill{display:inline-block;padding:5px 11px;border:1px solid #a6a6a6;border-radius:99px;font-size:.78rem}
.mode{border-color:#FAC775;color:#FAC775}.navbar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.navbar>div{max-width:1200px;margin:auto;display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding:10px 16px}
.navbar a{font-size:.85rem;text-decoration:none;border-radius:10px;padding:7px 10px}
.navbar a[aria-current="page"]{background:#7F77DD;color:white}
.navbar a:hover{background:var(--line)}.navbar button{margin-left:auto}
main{max-width:1200px;margin:auto;padding:26px 16px 70px}h2{font-size:1.3rem;margin:26px 0 12px}h3{font-size:1.05rem}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin-bottom:24px}
.kpi .tile,.panel,.card{background:var(--card);border-radius:16px;border:1px solid var(--line);box-shadow:0 7px 20px #0001}
.kpi .tile{padding:15px;border-top:4px solid var(--c)}.tile strong{font-size:1.65rem;display:block}.tile span{color:var(--muted);font-size:.79rem}
.panel{padding:19px;margin:16px 0;overflow-x:auto}.muted{color:var(--muted)}.columns{display:grid;grid-template-columns:2fr 1fr;gap:16px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line);font-size:.87rem}
code,pre,.log{font-family:ui-monospace,Menlo,Consolas,monospace}pre{overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}
.log{background:#15151a;color:#9FE1CB;border-left:4px solid #1D9E75;border-radius:10px;padding:12px}
button{border:none;background:#3974c4;color:#fff;padding:10px 15px;border-radius:10px;cursor:pointer}
button.secondary{background:#65636c}button:disabled{opacity:.45;cursor:not-allowed}
textarea{width:100%;min-height:90px;resize:vertical;background:var(--card);color:var(--text);border:1px solid var(--line);border-radius:10px;padding:11px}
.timeline{border-left:4px solid #7F77DD;margin-left:18px;padding-left:26px}.event{position:relative;background:var(--card);padding:15px;border-radius:15px;margin:16px 0;border:1px solid var(--line)}
.event:before{content:"";position:absolute;left:-38px;top:20px;width:16px;height:16px;border-radius:50%;background:var(--c);border:4px solid var(--bg)}
.event small{color:var(--muted)}.event h3{margin:4px 0}.event p{margin:4px 0}.chip{display:inline-block;font-size:.75rem;background:#7F77DD22;border:1px solid #7F77DD77;padding:2px 8px;border-radius:99px}
footer{border-top:1px solid var(--line);color:var(--muted);padding:22px;text-align:center;font-size:.78rem}
@media(max-width:760px){.columns{grid-template-columns:1fr}.navbar>div{gap:2px}.navbar a{font-size:.78rem;padding:7px}.hero{padding-top:28px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
"""

NAV = [
    ("/", "Cockpit"),
    ("/runs", "Incidents & Runs"),
    ("/timeline", "Timeline"),
    ("/twin", "Digital Twin"),
    ("/evidence", "Preuves"),
    ("/policy", "Policy / HITL"),
    ("/hitl", "HITL Inbox"),
    ("/copilot", "Copilot"),
    ("/itsm", "GLPI / ITSM"),
    ("/qualification", "Qualification"),
    ("/demo-studio", "Demo Studio"),
]

def esc(value):
    return html.escape(str(value), quote=True)

def shell(page, title, description, body, mode="MIXTE"):
    nav = "".join(
        f'<a href="{esc(path)}"'+(' aria-current="page"' if path==page else '')+f'>{esc(label)}</a>'
        for path,label in NAV
    )
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)} — ACME AIOps 2.0</title>
<style>{THEME}</style></head><body>
<header class="hero"><h1>ACME <span>AIOps 2.0</span> · {esc(title)}</h1>
<p>{esc(description)}</p><span class="pill mode">MODE {esc(mode)} · toute donnée synthétique est signalée</span></header>
<nav class="navbar" aria-label="Navigation principale"><div>{nav}
<button type="button" class="secondary" id="theme-toggle" aria-label="Changer le thème">◐ Thème</button></div></nav>
<main id="main">{body}</main>
<footer>ACME Digital Twin · AIOps 2.0 candidat · NO-GO production · Auteur : Abdelhalim Talbi</footer>
<script>
(function(){{var b=document.getElementById('theme-toggle');
b.addEventListener('click',function(){{var root=document.documentElement;root.dataset.theme=root.dataset.theme==='dark'?'light':'dark';}});
}})();
</script></body></html>'''

def panel(title,body):
    return f'<section class="panel"><h2>{esc(title)}</h2>{body}</section>'

def table(headers,rows):
    head="".join(f"<th scope='col'>{esc(h)}</th>" for h in headers)
    content="".join("<tr>"+"".join(f"<td>{esc(x)}</td>" for x in row)+"</tr>" for row in rows)
    if not content:
        content=f'<tr><td colspan="{len(headers)}">INCONNU — aucune donnée disponible</td></tr>'
    return f'<table><thead><tr>{head}</tr></thead><tbody>{content}</tbody></table>'

def pretty(value):
    return f'<pre class="log">{esc(json.dumps(value,indent=2,default=str,ensure_ascii=False))}</pre>'
