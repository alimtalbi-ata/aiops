"""Opt-in GAMMA POST boundary for fenced collector admission.

Call before legacy routing, only on the dedicated fenced instance. A false
return delegates to an explicitly audited non-publication route. The caller
must supply an external restore guard and existing private authority and witness DBs.
No deployment, actions or automatic authority initialization here.
"""
import json
from collector_admission_service import publish_guarded, lookup_guarded, bearer
from collector_admission_fence import require

ADMIT = '/api/v1/collector/admit'
RECEIPT = '/api/v1/collector/receipt'
DELEGATE = frozenset({
    '/api/v1/ingest', '/api/v1/hitl/dynamic/request', '/api/v1/hitl/dynamic/decide',
    '/api/v1/hitl/request', '/api/v1/hitl/decide', '/api/v1/glpi/preview',
    '/api/v1/mattermost/command', '/api/v1/enterprise-search',
    '/api/v1/enterprise-correlation/preview', '/api/v1/enterprise-correlation/historical',
    '/api/v1/enterprise-correlation/assessment', '/api/v1/enterprise-correlation/rag-context',
    '/api/v1/enterprise-correlation/ai-review', '/api/v1/ai-telemetry',
})


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def dispatch(handler, *, scope, authority, witness, restore_permitted, graph_reader, publish_records, read_context):
    """Return True if handled. Never fall back on any admission error."""
    if handler.path in DELEGATE:
        return False
    try:
        require(handler.path in (ADMIT, RECEIPT))
        host = '127.0.0.1:' + str(handler.server.server_port)
        for name, value in (('Host', host), ('Origin', 'http://' + host), ('Content-Type', 'application/json')):
            require(handler.headers.get_all(name) == [value])
        require(handler.headers.get_all('Transfer-Encoding') is None)
        auth = handler.headers.get_all('Authorization')
        lengths = handler.headers.get_all('Content-Length')
        require(auth is not None and len(auth) == 1 and lengths is not None and len(lengths) == 1)
        bearer(auth[0])
        length = int(lengths[0])
        require(0 < length <= 4096 and lengths[0] == str(length))
        require(restore_permitted() is True)
        raw = handler.rfile.read(length)
        require(len(raw) == length)
        body = json.loads(raw, object_pairs_hook=unique_object)
        keys = {'generation', 'rows'} if handler.path == ADMIT else {'generation', 'episode', 'batch'}
        require(isinstance(body, dict) and set(body) == keys and type(body['generation']) is int)
        with authority() as db, witness() as guard_db:
            args = dict(scope=scope, authorization=auth[0], generation=body['generation'])
            if handler.path == ADMIT:
                result = publish_guarded(db, guard_db, **args, rows=body['rows'], graph=graph_reader(), publish_records=publish_records,
                                 read_context=read_context)
            else:
                result = lookup_guarded(db, guard_db, **args, episode=body['episode'], batch=body['batch'])
        handler.reply(200, json.dumps(result, allow_nan=False).encode())
    except Exception:
        handler.reply(403, b'{"state":"UNKNOWN_BLOCKED","policy":"DENY"}')
    return True
