"""Read-only observability views; no arbitrary URL, PromQL or SQL from browsers."""
import json
import os
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi.responses import HTMLResponse
from portal.ui_theme import shell, panel, table, pretty, esc
from portal.twin_graph import graph_panel

# Queries are fixed server-side. No user-controlled PromQL or upstream URL.
QUERIES = {
    "up": "up",
    "core_requests": 'sum(rate(http_requests_total{job=~".*core.*"}[5m]))',
    "twin_requests": 'sum(rate(http_requests_total{job=~".*twin.*"}[5m]))',
    "postgres_up": 'pg_up',
}
PROMETHEUS_URL = os.getenv("PORTAL_PROMETHEUS_URL", "http://aiops2-prometheus:9090").rstrip("/")

def prometheus_query(key):
    if key not in QUERIES:
        raise ValueError("unsupported_metric")
    url = PROMETHEUS_URL + "/api/v1/query?" + urlencode({"query": QUERIES[key]})
    try:
        with urlopen(url, timeout=3) as response:
            if response.status != 200:
                return {"status": "UNKNOWN", "reason": "upstream_http_error"}
            payload = json.load(response)
        if payload.get("status") != "success" or payload.get("data", {}).get("resultType") != "vector":
            return {"status": "UNKNOWN", "reason": "unexpected_upstream_response"}
        results = payload["data"].get("result", [])
        if not isinstance(results, list):
            return {"status": "UNKNOWN", "reason": "unexpected_upstream_response"}
        return {"status": "OK", "items": results[:100], "truncated": len(results)>100}
    except (OSError, ValueError, KeyError, TypeError, HTTPError, URLError):
        return {"status": "UNKNOWN", "reason": "prometheus_unavailable"}

def _metrics_table(data, limit=30):
    if data.get("status") != "OK":
        return '<p class="muted">INCONNU — source indisponible ou réponse non qualifiée.</p>'
    rows = []
    for entry in data.get("items", [])[:limit]:
        if not isinstance(entry, dict):
            continue
        metric = entry.get("metric", {})
        value = entry.get("value", [])
        if not isinstance(metric, dict) or not isinstance(value, list) or len(value)<2:
            continue
        labels = ", ".join(f"{k}={v}" for k,v in sorted(metric.items()) if k in ("job","instance","service","namespace"))
        rows.append((labels or "sans labels", value[1], value[0]))
    return table(["Cible / labels", "Valeur", "Timestamp"], rows) + ('<p class="muted">Résultats limités à 100 séries.</p>' if data.get("truncated") else "")

def register_views(app, get_core, get_twin):
    @app.get("/prometheus", response_class=HTMLResponse)
    def prometheus_page():
        up = prometheus_query("up")
        body = panel("Disponibilité des cibles Prometheus", _metrics_table(up, 100))
        for key, title in (("core_requests", "Core — requêtes par seconde"), ("twin_requests", "Twin — requêtes par seconde")):
            body += panel(title, _metrics_table(prometheus_query(key)))
        body += panel("Provenance", "<p>API Prometheus, requêtes PromQL fixes côté serveur. Une métrique absente ne prouve ni panne ni bonne santé. Pas de requête libre ni d'accès direct du navigateur à Prometheus.</p>")
        return shell("/prometheus", "Prometheus", "Supervision en lecture seule, données live ou état INCONNU.", body, mode="LECTURE SEULE")

    @app.get("/databases", response_class=HTMLResponse)
    def databases_page():
        core = get_core("/health")
        pg = prometheus_query("postgres_up")
        core_state = core.get("status", "UNKNOWN") if isinstance(core, dict) else "UNKNOWN"
        body = panel("Connectivité applicative", table(["Service", "État déclaré", "Source"], [("Core", core_state, "Core /health")]))
        body += panel("Exporters PostgreSQL (si configurés)", _metrics_table(pg))
        body += panel("Périmètre et limites", "<p>Cette page ne se connecte pas à PostgreSQL et n'exécute aucune requête SQL. Le healthcheck Core ne certifie pas la disponibilité de toutes les bases. Sans exporter PostgreSQL qualifié, la santé SQL reste INCONNUE. Aucune donnée sensible ou identifiant de connexion n'est exposé.</p>")
        return shell("/databases", "Databases", "Visibilité des bases à partir de signaux de supervision qualifiables.", body, mode="LECTURE SEULE")

    @app.get("/cmdb", response_class=HTMLResponse)
    def cmdb_page():
        graph = get_twin("/api/twin/graph")
        nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
        edges = graph.get("edges", []) if isinstance(graph, dict) else []
        if not isinstance(nodes, list): nodes = []
        if not isinstance(edges, list): edges = []
        body = panel("Origine des données", "<p>Source : registre Digital Twin, et non CMDB GLPI autoritative. L'inventaire GLPI n'est pas synchronisé ou vérifié par cette vue. Aucune correspondance CI n'est inventée.</p>")
        body += graph_panel(graph)
        body += panel("Éléments de configuration Twin", table(["Identifiant", "Type", "Site", "État"], [
            (n.get("node_id", "INCONNU"), n.get("type", "INCONNU"), n.get("site", "INCONNU"), n.get("state", "INCONNU"))
            for n in nodes[:200] if isinstance(n, dict)]))
        body += panel("Dépendances Twin", table(["Source", "Relation", "Cible"], [
            (e.get("source_id", "INCONNU"), e.get("relation_type", "INCONNU"), e.get("target_id", "INCONNU"))
            for e in edges[:300] if isinstance(e, dict)]))
        return shell("/cmdb", "CMDB & dépendances", "Vue de topologie Twin, provenance explicite et limites GLPI.", body, mode="LECTURE SEULE")
