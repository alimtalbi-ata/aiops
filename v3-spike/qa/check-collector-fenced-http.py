"""QA: actual collector + HTTP fence fixture; no real GAMMA or production actions."""
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
from unittest.mock import patch
from urllib.request import build_opener, ProxyHandler, Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vertical'))
import continuous_collector as collector
from durable_collector import DurableCollector


@contextmanager
def server(handler):
    with HTTPServer(('127.0.0.1', 0), handler) as s:
        t = threading.Thread(target=s.serve_forever, daemon=True)
        t.start()
        try:
            yield s
        finally:
            s.shutdown()
            t.join()


def backup(source, dest):
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(dest)) as dst:
        src.backup(dst)
    dest.chmod(0o600)


def campaign(root, lose_ack, fenced):
    journal = root / 'journal'
    journal.mkdir(mode=0o700)
    authority = root / 'authority.sqlite3'
    old = root / 'old.sqlite3'
    token = secrets.token_hex(32)
    scope = 'synthetic-demo/collector/target'
    with closing(sqlite3.connect(authority)) as db, db:
        db.execute('CREATE TABLE fence (scope TEXT PRIMARY KEY, generation INTEGER, state TEXT)')
        db.execute('CREATE TABLE receipts (episode TEXT PRIMARY KEY, run_id TEXT UNIQUE)')
        db.execute('INSERT INTO fence VALUES (?,0,?)', (scope, 'ARMED'))
    counts = dict(health=0, admission=0, rejected=0, committed=0)
    delay = .01

    class Quiet(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

    class Target(Quiet):
        def do_GET(self):
            assert self.path == '/health'
            counts['health'] += 1
            time.sleep(delay)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')

    class Admission(Quiet):
        def do_POST(self):
            assert self.path == '/api/v1/ingest/admit'
            rows = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert len(rows) == 3 and all(r['synthetic'] is True for r in rows)
            counts['admission'] += 1
            episode = rows[0]['id'].removesuffix('-baseline')
            allowed = False
            with closing(sqlite3.connect(authority)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                state = db.execute('SELECT generation,state FROM fence WHERE scope=?', (scope,)).fetchone()
                if not fenced or (hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)
                                  and self.headers.get('X-Scope') == scope
                                  and state == (0, 'ARMED') and self.headers.get('X-Generation') == '0'):
                    rid = f"RUN-{counts['committed'] + 1:016X}"
                    db.execute('INSERT INTO receipts VALUES (?,?)', (episode, rid))
                    db.execute('UPDATE fence SET generation=generation+1,state=? WHERE scope=?', ('LATCHED', scope))
                    allowed = True
            if not allowed:
                counts['rejected'] += 1
                self.send_response(409)
                self.end_headers()
                return
            counts['committed'] += 1
            if lose_ack and counts['committed'] == 1:
                self.close_connection = True
                return
            response = {'admission': {'classification': 'SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1', 'admitted': True, 'operational_decision': 'DENY', 'production_authorized': False}, 'publication': {'core': {'run': {'run_id': rid, 'mode': 'DEMO', 'status': 'CREATED'}}, 'stored_evidence': [{}, {}, {}]}, 'production_authorized': False}
            self.send_response(200)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

    # Adapter fixture: an old collector snapshot retains generation zero.
    # The real product does not yet transmit these credentials or generation.
    def admit(port, rows):
        origin = f'http://127.0.0.1:{port}'
        req = Request(origin + '/api/v1/ingest/admit', data=json.dumps(rows).encode(),
                      headers={'Origin': origin, 'Content-Type': 'application/json',
                               'Authorization': 'Bearer ' + token, 'X-Scope': scope, 'X-Generation': '0'})
        with build_opener(ProxyHandler({}), collector.NoRedirect()).open(req, timeout=5) as res:
            return json.loads(res.read(65536))

    with server(Target) as target, server(Admission) as admission, patch.object(collector, 'admission', admit):
        args = (target.server_port, admission.server_port, journal)
        with DurableCollector(*args, initialize=True) as c:
            c.observe()
            assert c.observe()['state'] == 'ARMED'
        backup(journal / 'collector.sqlite3', old)
        delay = .12
        with DurableCollector(*args) as c:
            c.observe()
            assert c.observe()['state'] == ('UNKNOWN_BLOCKED' if lose_ack else 'LATCHED')
        with DurableCollector(*args) as c:
            c.observe()
            c.observe()
        assert counts['committed'] == 1
        backup(old, journal / 'collector.sqlite3')
        with DurableCollector(*args) as c:
            c.observe()
            restored = c.observe()
        with closing(sqlite3.connect(authority)) as db:
            receipts = db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]
        assert counts['admission'] == 2 and receipts == counts['committed']
        if fenced:
            assert receipts == 1 and counts['rejected'] == 1 and restored['state'] == 'UNKNOWN_BLOCKED'
        else:
            assert receipts == 2 and counts['rejected'] == 0 and restored['state'] == 'LATCHED'
    return dict(fenced=fenced, lost_ack=lose_ack, receipts=receipts, restored_state=restored['state'], **counts)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='v3-fenced-http-') as tmp:
        results = []
        for fenced in (False, True):
            for lost in (False, True):
                root = Path(tmp) / f'{fenced}-{lost}'
                root.mkdir(mode=0o700)
                results.append(campaign(root, lost, fenced))
        print(json.dumps({'classification': 'V3_QA_FENCED_HTTP_FIXTURE', 'result': 'PASS', 'cases': results, 'production_authorized': False, 'limitations': ['Test-only HTTP adapter and synthetic admission; no GAMMA/Core/Evidence', 'No recovery evidence validation, rearm or simultaneous authority rollback', 'Atomic fixture receipts only; external effects not qualified']}, sort_keys=True))
