"""Read-only exploration API. No incident mutation, workflow execution or GLPI writes."""
from __future__ import annotations
import ipaddress
import json
import os
import re
import time
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request as URLRequest, urlopen
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/explorer", tags=["explorer"])
api = APIRouter(prefix="/api/explorer", tags=["explorer"])
ROOT = os.path.dirname(__file__)
MAX_ROWS = 200
MAX_SECONDS = 8
MAX_RANGE_POINTS = 1000
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z_0-9]{0,62}$")
SQL_FORBIDDEN = re.compile(r"(;|--|/\*|\*/|\x00)")
SQL_START = re.compile(r"^\s*SELECT\s", re.IGNORECASE)
SQL_DANGEROUS = re.compile(r"\b(?:INTO\s+(?:OUTFILE|DUMPFILE)|LOAD_FILE\s*\(|PG_SLEEP\s*\(|SLEEP\s*\(|PG_ADVISORY_[A-Z_]+\s*\(|DBLINK\s*\(|LO_EXPORT\s*\() ", re.IGNORECASE | re.VERBOSE)
DATA_SOURCES = {
    "core": ("postgres", "EXPLORER_CORE_PG_DSN"),
    "temporal": ("postgres", "EXPLORER_TEMPORAL_PG_DSN"),
    "glpi": ("mariadb", "EXPLORER_GLPI_MYSQL_DSN"),
}
UPSTREAMS = {
    "prometheus": ("EXPLORER_PROMETHEUS_URL", "http://aiops2-prometheus:9090"),
    "loki": ("EXPLORER_LOKI_URL", ""),
    "tempo": ("EXPLORER_TEMPO_URL", ""),
    "temporal": ("EXPLORER_TEMPORAL_UI_URL", ""),
    "n8n": ("EXPLORER_N8N_URL", ""),
    "cmdb": ("EXPLORER_CMDB_URL", ""),
    "core": ("EXPLORER_CORE_URL", "http://aiops2-rebuild-core:810"),
}
# Only explicitly supported read-only API paths, never arbitrary URLs.
PATHS = {
    "prometheus": {"query": "/api/v1/query", "query_range": "/api/v1/query_range",
                   "targets": "/api/v1/targets", "rules": "/api/v1/rules",
                   "alerts": "/api/v1/alerts", "labels": "/api/v1/labels"},
    "loki": {"labels": "/loki/api/v1/labels", "query_range": "/loki/api/v1/query_range"},
    "tempo": {"trace": "/api/traces/{trace_id}"},
    "cmdb": {"health": "/health"},
    "core": {"dashboard": "/api/dashboard", "incidents": "/api/incidents",
             "runs": "/api/runs", "scenarios": "/api/scenarios"},
    "temporal": {"health": "/", "namespaces": "/api/v1/namespaces"},
    "n8n": {"health": "/healthz", "workflows": "/api/v1/workflows", "executions": "/api/v1/executions"},
}
ALLOWED_PARAMS = {
    "query": {"query", "time", "limit"},
    "query_range": {"query", "start", "end", "step", "limit"},
    "targets": {"state"},
    "rules": {"type"},
    "alerts": {},
    "labels": {"start", "end"},
    "trace": {},
    "health": {},
    "namespaces": {},
    "dashboard": {},
    "incidents": {},
    "runs": {},
    "scenarios": {},
    "workflows": {"limit", "cursor", "active"},
    "executions": {"limit", "cursor", "status", "workflowId"},
}
LIMITED_FIELDS = {"query": 2048, "time": 40, "start": 40, "end": 40, "step": 20,
                  "state": 20, "type": 20, "limit": 5, "cursor": 512, "active": 5,
                  "status": 24, "workflowId": 64}

def _deny_untrusted(request: Request):
    raw = os.getenv("EXPLORER_ALLOWED_CIDRS", "")
    if not raw:
        raise HTTPException(503, "explorer_network_allowlist_not_configured")
    peer = request.client.host if request.client else ""
    try:
        ip = ipaddress.ip_address(peer)
        networks = [ipaddress.ip_network(item.strip(), strict=False) for item in raw.split(",") if item.strip()]
        if not networks or not any(ip in net for net in networks):
            raise HTTPException(403, "explorer_network_denied")
    except ValueError:
        raise HTTPException(503, "explorer_network_allowlist_invalid")

def _check(request: Request):
    _deny_untrusted(request)
    if os.getenv("EXPLORER_ENABLED", "0") != "1":
        raise HTTPException(503, "explorer_disabled")

def _upstream(service):
    key, fallback = UPSTREAMS[service]
    url = os.getenv(key, fallback).strip().rstrip("/")
    if not url:
        raise HTTPException(503, service + "_not_configured")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise HTTPException(503, service + "_invalid_configuration")
    return url

def _read(service, path, params=None):
    url = _upstream(service) + path
    if params:
        url += "?" + urlencode(params)
    headers = {"Accept": "application/json"}
    if service == "n8n" and path.startswith("/api/v1/"):
        api_key = os.getenv("EXPLORER_N8N_API_KEY", "")
        if not api_key:
            raise HTTPException(503, "n8n_read_api_not_configured")
        headers["X-N8N-API-KEY"] = api_key
    try:
        with urlopen(URLRequest(url, headers=headers), timeout=MAX_SECONDS) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise HTTPException(502, "upstream_response_too_large")
            if service in ("temporal", "n8n") and path in ("/", "/healthz"):
                try:
                    payload = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    payload = None
                return {"service": service, "reachable": True,
                        "http_status": response.status,
                        "content_type": response.headers.get("Content-Type", ""),
                        "details": payload if isinstance(payload, dict) else None}
            return json.loads(raw)
    except HTTPError as exc:
        if service == "n8n" and exc.code in (401, 403):
            raise HTTPException(503, "n8n_read_api_credentials_rejected") from None
        raise HTTPException(502, service + "_unavailable") from None
    except (URLError, TimeoutError, ValueError):
        raise HTTPException(502, service + "_unavailable") from None

@router.get("/{page}")
def page(page: str, request: Request):
    _check(request)
    if page not in {"databases", "prometheus", "alerts", "cmdb", "logs", "traces", "orchestration", "core"}:
        raise HTTPException(404)
    response = FileResponse(os.path.join(ROOT, "explorer_ui.html"), media_type="text/html")
    response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store"
    return response

@router.get("/assets/explorer.js", include_in_schema=False)
def script(request: Request):
    _check(request)
    return FileResponse(os.path.join(ROOT, "explorer_ui.js"), media_type="application/javascript")

@api.get("/catalog")
def catalog(request: Request):
    _check(request)
    return {"databases": [{"id": k, "engine": engine, "configured": bool(os.getenv(env))}
                          for k, (engine, env) in DATA_SOURCES.items()],
            "services": {name: bool(os.getenv(key, default)) for name, (key, default) in UPSTREAMS.items()},
            "mode": "read-only", "max_rows": MAX_ROWS}

@api.get("/observability/{service}/{operation}")
def observe(service: str, operation: str, request: Request):
    _check(request)
    if service not in PATHS or operation not in PATHS[service] or operation == "trace":
        raise HTTPException(404)
    allowed = ALLOWED_PARAMS[operation]
    params = dict(request.query_params)
    if any(k not in allowed or len(v) > LIMITED_FIELDS.get(k, 40) for k, v in params.items()):
        raise HTTPException(400, "invalid_parameters")
    if service == "n8n" and operation in {"workflows", "executions"}:
        try:
            if "limit" in params and not 1 <= int(params["limit"]) <= 100:
                raise ValueError
        except ValueError:
            raise HTTPException(400, "invalid_limit")
    if operation in {"query", "query_range"} and not params.get("query"):
        raise HTTPException(400, "query_required")
    if operation == "query_range":
        try:
            start, end, step = float(params["start"]), float(params["end"]), float(params["step"])
            if not (0 < step <= 86400 and start <= end and (end - start) / step <= MAX_RANGE_POINTS):
                raise ValueError
        except (KeyError, ValueError, OverflowError):
            raise HTTPException(400, "invalid_time_range")
    return _read(service, PATHS[service][operation], params)

GLPI_TYPES = frozenset(("Computer", "NetworkEquipment", "Monitor", "Printer", "Software"))

def _glpi_inventory(kind, item_id=None, offset=0, limit=25):
    if kind not in GLPI_TYPES:
        raise HTTPException(404, "unknown_inventory_type")
    if item_id is not None and item_id < 1:
        raise HTTPException(400, "invalid_inventory_id")
    if not 0 <= offset <= 100000 or not 1 <= limit <= 100:
        raise HTTPException(400, "invalid_inventory_page")
    base = os.getenv("GLPI_API_URL", "").rstrip("/")
    app_token = os.getenv("GLPI_APP_TOKEN", "")
    user_token = os.getenv("GLPI_USER_TOKEN", "")
    parsed = urlsplit(base)
    if not all((base, app_token, user_token)) or parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(503, "glpi_inventory_not_configured")
    def call(path, session=None, payload=None):
        headers = {"App-Token": app_token, "Accept": "application/json"}
        if session:
            headers["Session-Token"] = session
        else:
            headers["Authorization"] = "user_token " + user_token
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode()
        req = URLRequest(base + "/" + path, data=body, headers=headers,
                         method="POST" if payload is not None else "GET")
        with urlopen(req, timeout=MAX_SECONDS) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise HTTPException(502, "glpi_inventory_response_too_large")
            return json.loads(raw) if raw else None
    session = None
    try:
        initial = call("initSession")
        session = initial.get("session_token") if isinstance(initial, dict) else None
        if not session:
            raise HTTPException(502, "glpi_session_unavailable")
        call("changeActiveProfile", session, {"profiles_id": 6})
        active = call("getActiveProfile", session)
        profile = active.get("active_profile", {}) if isinstance(active, dict) else {}
        if profile.get("id") != 6:
            raise HTTPException(403, "glpi_technician_profile_unavailable")
        path = kind + ("/" + str(item_id) if item_id is not None else
                       "/?range=" + str(offset) + "-" + str(offset + limit - 1))
        result = call(path, session)
        if item_id is not None:
            if not isinstance(result, dict):
                raise HTTPException(502, "glpi_inventory_unexpected_response")
            return result
        if not isinstance(result, list):
            raise HTTPException(502, "glpi_inventory_unexpected_response")
        return {"items": result[:limit], "returned": min(len(result), limit),
                "offset": offset, "limit": limit, "truncated_possible": len(result) >= limit}
    except HTTPException:
        raise
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise HTTPException(403, "glpi_inventory_access_denied") from None
        raise HTTPException(502, "glpi_inventory_unavailable") from None
    except (URLError, TimeoutError, ValueError, KeyError, AttributeError):
        raise HTTPException(502, "glpi_inventory_unavailable") from None
    finally:
        if session:
            try:
                call("killSession", session)
            except Exception:
                pass

@api.get("/cmdb/inventory/{kind}")
def inventory_list(kind: str, request: Request, offset: int = 0, limit: int = 25):
    _check(request)
    return _glpi_inventory(kind, offset=offset, limit=limit)

@api.get("/cmdb/inventory/{kind}/{item_id}")
def inventory_detail(kind: str, item_id: int, request: Request):
    _check(request)
    return _glpi_inventory(kind, item_id=item_id)

@api.get("/core/{collection}")
def core_collection(collection: str, request: Request, limit: int = 100):
    _check(request)
    if collection not in {"dashboard", "incidents", "runs", "scenarios"}:
        raise HTTPException(404, "unknown_core_collection")
    if not 1 <= limit <= MAX_ROWS:
        raise HTTPException(400, "invalid_limit")
    payload = _read("core", PATHS["core"][collection])
    if not isinstance(payload, dict):
        raise HTTPException(502, "core_unexpected_response")
    if collection == "dashboard":
        return payload
    items = payload.get("items")
    if not isinstance(items, list):
        raise HTTPException(502, "core_unexpected_response")
    return {"items": items[:limit], "returned": min(len(items), limit),
            "upstream_returned": len(items), "truncated": len(items) > limit}

@api.get("/temporal/namespaces/{namespace}/workflows")
def temporal_workflows(namespace: str, request: Request, pagesize: int = 25):
    _check(request)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}", namespace):
        raise HTTPException(400, "invalid_namespace")
    if not 1 <= pagesize <= 100:
        raise HTTPException(400, "invalid_pagesize")
    payload = _read("temporal", "/api/v1/namespaces/" + namespace + "/workflows",
                    {"pagesize": pagesize})
    if not isinstance(payload, dict) or not isinstance(payload.get("executions"), list):
        raise HTTPException(502, "temporal_unexpected_response")
    executions = payload["executions"]
    return {"executions": executions[:pagesize], "returned": min(len(executions), pagesize),
            "upstream_returned": len(executions), "truncated": len(executions) > pagesize}

@api.get("/tempo/search")
def tempo_search(request: Request, minutes: int = 60, limit: int = 20):
    _check(request)
    if minutes not in (15, 60, 360, 1440) or not 1 <= limit <= 100:
        raise HTTPException(400, "invalid_search_window")
    end = int(time.time())
    payload = _read("tempo", "/api/search",
                    {"start": end - minutes * 60, "end": end, "limit": limit})
    if not isinstance(payload, dict) or not isinstance(payload.get("traces"), list):
        raise HTTPException(502, "tempo_unexpected_response")
    traces = payload["traces"]
    return {"traces": traces[:limit], "returned": min(len(traces), limit),
            "upstream_returned": len(traces), "truncated": len(traces) > limit,
            "metrics": payload.get("metrics", {})}

@api.get("/observability/tempo/trace/{trace_id}")
def trace(trace_id: str, request: Request):
    _check(request)
    if not re.fullmatch(r"[a-fA-F0-9]{16}|[a-fA-F0-9]{32}", trace_id):
        raise HTTPException(400, "invalid_trace_id")
    return _read("tempo", "/api/traces/" + trace_id)

def _source(source):
    if source not in DATA_SOURCES:
        raise HTTPException(404, "unknown_database")
    engine, key = DATA_SOURCES[source]
    dsn = os.getenv(key, "").strip()
    if not dsn:
        raise HTTPException(503, "database_not_configured")
    return engine, dsn

def _connection(source):
    engine, dsn = _source(source)
    if engine == "postgres":
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(dsn, connect_timeout=4, row_factory=dict_row,
                               options="-c default_transaction_read_only=on -c statement_timeout=8000 -c lock_timeout=1000")
        conn.read_only = True
        return conn, engine
    try:
        import pymysql
        from urllib.parse import unquote
    except ImportError:
        raise HTTPException(503, "mariadb_driver_not_installed")
    u = urlsplit(dsn)
    if u.scheme != "mysql" or not u.hostname or not u.username or u.password is None or not u.path:
        raise HTTPException(503, "mariadb_dsn_invalid")
    conn = pymysql.connect(host=u.hostname, port=u.port or 3306,
                           user=unquote(u.username), password=unquote(u.password),
                           database=unquote(u.path.lstrip("/")), connect_timeout=4,
                           read_timeout=MAX_SECONDS, write_timeout=MAX_SECONDS,
                           cursorclass=pymysql.cursors.DictCursor, autocommit=False)
    with conn.cursor() as cursor:
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.execute("SET SESSION MAX_EXECUTION_TIME=8000")
    return conn, engine

def _safe_query(sql):
    if not isinstance(sql, str) or not 1 <= len(sql) <= 4000 or SQL_FORBIDDEN.search(sql) or not SQL_START.match(sql) or SQL_DANGEROUS.search(sql):
        raise HTTPException(400, "only_single_select_allowed")
    # Role privileges and read-only transaction are mandatory enforcement.
    return sql.strip()

def _run(source, sql, limit):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_ROWS:
        raise HTTPException(400, "invalid_limit")
    sql = _safe_query(sql)
    try:
        conn, engine = _connection(source)
        with closing(conn):
            with conn.cursor() as cur:
                if engine == "postgres":
                    cur.execute("SET TRANSACTION READ ONLY")
                else:
                    cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT * FROM (" + sql + ") AS explorer_result LIMIT " + str(limit))
                rows = cur.fetchall()
                cols = [col.name if hasattr(col, "name") else col[0] for col in cur.description]
                return {"columns": cols, "rows": [dict(row) for row in rows],
                        "limit": limit, "truncated_possible": len(rows) == limit}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "database_query_failed")

@api.get("/databases/{source}/tables")
def tables(source: str, request: Request):
    _check(request)
    engine, _ = _source(source)
    if engine == "postgres":
        sql = "SELECT table_schema AS schema_name, table_name FROM information_schema.tables WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2"
    else:
        sql = "SELECT table_schema AS schema_name, table_name FROM information_schema.tables WHERE table_type='BASE TABLE' AND table_schema=DATABASE() ORDER BY 1,2"
    return _run(source, sql, MAX_ROWS)

@api.get("/databases/{source}/columns")
def columns(source: str, request: Request, schema: str, table: str):
    _check(request)
    if not IDENTIFIER.fullmatch(schema) or not IDENTIFIER.fullmatch(table):
        raise HTTPException(400, "invalid_identifier")
    engine, _ = _source(source)
    if engine == "mariadb" and schema != urlsplit(_source(source)[1]).path.lstrip("/"):
        raise HTTPException(400, "schema_not_allowed")
    if engine == "postgres":
        sql = ("SELECT column_name, data_type, is_nullable FROM information_schema.columns "
               "WHERE table_schema='" + schema + "' AND table_name='" + table + "' ORDER BY ordinal_position")
    else:
        sql = ("SELECT column_name, data_type, is_nullable FROM information_schema.columns "
               "WHERE table_schema=DATABASE() AND table_name='" + table + "' ORDER BY ordinal_position")
    return _run(source, sql, MAX_ROWS)

@api.get("/databases/{source}/preview")
def preview(source: str, request: Request, schema: str, table: str, limit: int = 25, offset: int = 0):
    _check(request)
    if not IDENTIFIER.fullmatch(schema) or not IDENTIFIER.fullmatch(table):
        raise HTTPException(400, "invalid_identifier")
    if not isinstance(offset, int) or offset < 0 or offset > 100000:
        raise HTTPException(400, "invalid_offset")
    engine, _ = _source(source)
    if engine == "mariadb":
        configured_schema = urlsplit(_source(source)[1]).path.lstrip("/")
        if schema != configured_schema:
            raise HTTPException(400, "schema_not_allowed")
    quote = '"' if engine == "postgres" else '`'
    qualified = quote + schema + quote + "." + quote + table + quote
    return _run(source, "SELECT * FROM " + qualified + " LIMIT " + str(limit) +
                " OFFSET " + str(offset), limit)

@api.post("/databases/{source}/query")
async def query(source: str, request: Request):
    _check(request)
    if int(request.headers.get("content-length", "0") or "0") > 6000:
        raise HTTPException(413, "request_too_large")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "invalid_json")
    if not isinstance(payload, dict) or set(payload) - {"sql", "limit"}:
        raise HTTPException(400, "invalid_request")
    return _run(source, payload.get("sql"), payload.get("limit", 100))

def mount(app):
    app.include_router(router)
    app.include_router(api)
