from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get('/mission-control', response_class=HTMLResponse, include_in_schema=False)
def mission_control():
    return HTMLResponse(Path(__file__).with_name('mission_control.html').read_text(encoding='utf-8'), headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin', 'Content-Security-Policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
