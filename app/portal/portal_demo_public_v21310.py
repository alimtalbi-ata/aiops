"""Public synthetic-only storyboard. No operational API writes or Core exports."""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

router = APIRouter()
ASSET = Path(__file__).resolve().parent / "public_demo_assets" / "AIOPS-EXECUTIVE-THEATER-PUBLIC.html"
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'self' 'unsafe-inline' data:; connect-src 'none'; frame-ancestors 'self'",
}

@router.get("/demo/", response_class=HTMLResponse)
def catalog():
    html = """<!doctype html><html lang="fr"><meta charset="utf-8"><title>AIOps Demo Center</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <body style="font:16px system-ui;max-width:850px;margin:3rem auto;padding:1rem">
    <a href="/demo-studio">← Demo Studio</a> · <a href="/">Portail AIOps</a>
    <h1>Demo Center — scénario fictif</h1>
    <p>Simulation STAR en lecture seule. Aucun incident créé, aucune remédiation, aucun export Core publié.</p>
    <p><a href="/demo/star">Ouvrir Executive Theater STAR</a></p>
    <p>Les replays Core et Evidence restent protégés et désactivés.</p></body></html>"""
    return HTMLResponse(html, headers=HEADERS)

@router.get("/demo/star")
def star():
    if not ASSET.is_file() or ASSET.is_symlink():
        raise HTTPException(503, "synthetic demo asset unavailable")
    return FileResponse(ASSET, media_type="text/html", headers=HEADERS)
