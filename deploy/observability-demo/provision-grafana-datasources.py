#!/usr/bin/env python3
"""Safely create Loki and Tempo datasources in existing Grafana (no restart)."""
import base64
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000").rstrip("/")
USER = os.environ.get("GRAFANA_USER", "admin")
NAMES = [
    ("AIOps2 Demo Loki", "loki", "http://demo-loki:3100"),
    ("AIOps2 Demo Tempo", "tempo", "http://demo-tempo:3200"),
]

if not (BASE.startswith("http://127.0.0.1:") or BASE.startswith("http://localhost:") or BASE.startswith("https://")):
    sys.exit("REFUS: URL Grafana non locale en HTTP; utiliser HTTPS ou loopback.")
password = os.environ.get("GRAFANA_PASSWORD") or getpass.getpass("Mot de passe Grafana (non affiché) : ")
if not password:
    sys.exit("Mot de passe vide.")
auth = "Basic " + base64.b64encode(f"{USER}:{password}".encode()).decode()

def api(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Authorization": auth, "Accept": "application/json", "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        # Never expose auth headers, passwords, or arbitrary server response.
        raise RuntimeError(f"{method} {path}: HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {path}: connexion impossible ({exc.reason})") from None

try:
    _, health = api("GET", "/api/health")
    _, existing = api("GET", "/api/datasources")
    if not isinstance(existing, list):
        raise RuntimeError("Réponse /api/datasources inattendue")
    print("Grafana:", health.get("version", "version inconnue"))
    print("Datasources existantes:", len(existing))
    for name, kind, url in NAMES:
        matches = [ds for ds in existing if ds.get("name") == name]
        if matches:
            ds = matches[0]
            if ds.get("type") != kind or ds.get("url", "").rstrip("/") != url:
                raise RuntimeError(f"CONFLIT {name}: datasource existante différente, aucune modification")
            print(f"EXISTE: {name} (uid={ds.get('uid')})")
            continue
        payload = {
            "name": name, "type": kind, "access": "proxy", "url": url,
            "isDefault": False, "basicAuth": False,
            "jsonData": {"httpMethod": "GET"} if kind == "loki" else {},
        }
        status, result = api("POST", "/api/datasources", payload)
        print(f"CRÉÉE: {name} (HTTP {status}, uid={result.get('datasource', {}).get('uid', 'inconnu')})")
    print("FIN: datasources créées ou vérifiées; tester Save & test / API health dans Grafana.")
except RuntimeError as exc:
    sys.exit(f"ÉCHEC CONTRÔLÉ: {exc}")
