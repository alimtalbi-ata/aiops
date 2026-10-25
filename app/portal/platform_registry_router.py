"""Static, read-only component inventory mounted on the existing portal app.

This route has no upstream connections. It must never represent registry rows as
healthy or runtime-attested; connection routes require a separate reviewed adapter.
"""
import html
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from portal.platform_registry import build_portal_component_registry

router = APIRouter()
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; connect-src 'none'; img-src 'none'; "
                               "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; "
                               "frame-ancestors 'none'",
}


def _exact_get_paths(request: Request) -> set[str]:
    """Read only this ASGI application's exact GET paths; never probe a backend."""
    paths = set()
    for route in request.app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if isinstance(path, str) and methods and "GET" in methods:
            paths.add(path)
    return paths


def _with_route_presence(payload: dict, request: Request) -> dict:
    """Annotate exact GET-path matches without claiming component integration."""
    paths = _exact_get_paths(request)
    payload["portal_route_presence_source"] = "IN_PROCESS_ASGI_ROUTE_TABLE"
    payload["portal_route_presence_scope"] = "EXACT_GET_PATH_ONLY"
    payload["portal_route_presence_is_runtime_attestation"] = False
    payload["items"] = [
        {
            **item,
            "portal_get_path_present": item["path"] in paths,
            "portal_get_path_evidence": (
                "EXACT_GET_PATH_MATCH" if item["path"] in paths else "NO_EXACT_GET_PATH"
            ),
        }
        for item in payload["items"]
    ]
    return payload


@router.get("/api/platform/components", name="static_platform_component_registry")
def platform_components(request: Request):
    """Return the static plan plus exact GET-path matches in this ASGI process."""
    payload = _with_route_presence(build_portal_component_registry(), request)
    payload.update({
        "source_mode": "STATIC_REGISTRY_PLAN",
        "component_observation_source": "ABSENT",
        "route_mount_attested": False,
        "runtime_e2e_qualified": False,
        "production_qualified": False,
    })
    return JSONResponse(content=payload, headers=HEADERS)


@router.get("/noc", response_class=HTMLResponse, name="static_noc_convergence_inventory")
def noc_convergence_inventory(request: Request):
    """Render a local, read-only convergence plan without implying runtime health.

    This is an operator-facing inventory surface, not a substitute for the NOC
    integration. It intentionally has no upstream provider, links, forms, scripts,
    polling, or client-controlled state. Operational components remain UNKNOWN
    until a separately authenticated and reviewed read model is integrated.
    """
    payload = _with_route_presence(build_portal_component_registry(), request)
    rows = []
    for item in payload["items"]:
        path_presence = (
            "PRÉSENTE · GET (CHEMIN UNIQUEMENT)"
            if item["portal_get_path_present"] else "ABSENTE · GET EXACT"
        )
        rows.append(
            '<tr class="component-row"><th scope="row">'
            + html.escape(item["name"], quote=True)
            + '</th><td><code>' + html.escape(item["path"], quote=True) + '</code></td>'
            + '<td>' + html.escape(path_presence, quote=True) + '</td>'
            + '<td><strong>INCONNU</strong></td>'
            + '<td>ABSENTE</td><td>NON · À INTÉGRER</td><td>NON</td></tr>'
        )
    body = (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>AIOps — inventaire de convergence NOC</title>'
        '<style>'
        'body{font:16px system-ui,sans-serif;max-width:1400px;margin:2rem auto;padding:0 1rem;color:#182233}'
        'h1{font-size:1.8rem}.warning{border-left:5px solid #b7791f;background:#fff4d6;padding:1rem}'
        '.meta{color:#46556a}table{border-collapse:collapse;width:100%;margin:1.4rem 0}'
        'caption{text-align:left;font-weight:700;padding:.7rem 0}'
        'th,td{border:1px solid #ccd4df;padding:.65rem;text-align:left;vertical-align:top}'
        'thead{background:#edf2f8}code{overflow-wrap:anywhere}'
        '@media(max-width:850px){table{font-size:.88rem}th,td{padding:.35rem}}'
        '</style></head><body><main>'
        '<h1>NOC AIOps — inventaire de convergence</h1>'
        '<p class="warning"><strong>PLAN STATIQUE — PAS UN ÉCRAN NOC RUNTIME.</strong> '
        'Cette page est servie localement par le portail existant. Elle ne contacte aucun backend. '
        'Aucun état, ticket, horodatage ou preuve runtime n’est observé ou attesté ; '
        'aucune remédiation LIVE n’est autorisée.</p>'
        '<p class="meta">Entrée cible : <code>'
        + html.escape(payload["entrypoint"], quote=True)
        + '</code> · Source : <code>STATIC_REGISTRY_PLAN</code> · '
        'Observation : <code>ABSENT</code> · Qualification production : <code>NON</code></p>'
        '<table><caption>Composants prévus — états inconnus jusqu’à intégration authentifiée</caption>'
        '<thead><tr><th scope="col">Composant</th><th scope="col">Chemin cible (plan)</th>'
        '<th scope="col">GET exact dans le code</th><th scope="col">État observé</th>'
        '<th scope="col">Observation</th><th scope="col">Route métier</th>'
        '<th scope="col">Auth runtime</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
        '<p class="meta">« PRÉSENTE · GET » signifie uniquement que le chemin exact existe dans la table ASGI de ce processus ; '
        'cela ne prouve ni le raccordement au produit, ni son authentification, ni son état runtime. '
        'Chaque famille reste à intégrer et aucun chemin du tableau n’est un lien activé. '
        'Cette page statique ne contacte aucun backend Checkmk/Thruk, GLPI, n8n, Grafana, Prometheus, '
        'Temporal, DGX, RAG, CMDB, Policy, HITL ou Evidence.</p>'
        '</main></body></html>'
    )
    return HTMLResponse(content=body, headers=HEADERS)
