"""QA regression: real loopback HTTP and SQLite; synthetic admission, no GAMMA."""
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vertical'))
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


def campaign(root, lose_ack):
    journal = root / 'journal'
    journal.mkdir(mode=0o700)
    db = journal / 'collector.sqlite3'
    old = root / 'old.sqlite3'
    ledger = root / 'admission.sqlite3'
    with closing(sqlite3.connect(ledger)) as c, c:
        c.execute('CREATE TABLE publications (identity TEXT PRIMARY KEY, run_id TEXT UNIQUE)')
    counts = {'health': 0, 'admission': 0}
    delay = 0.01

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
            identity = rows[0]['id'].removesuffix('-baseline')
            counts['admission'] += 1
            rid = f"RUN-{counts['admission']:016X}"
            with closing(sqlite3.connect(ledger)) as c, c:
                c.execute('INSERT INTO publications VALUES (?, ?)', (identity, rid))
            if lose_ack and counts['admission'] == 1:
                self.close_connection = True
                return
            response = {'admission': {'classification': 'SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1', 'admitted': True, 'operational_decision': 'DENY', 'production_authorized': False}, 'publication': {'core': {'run': {'run_id': rid, 'mode': 'DEMO', 'status': 'CREATED'}}, 'stored_evidence': [{}, {}, {}]}, 'production_authorized': False}
            self.send_response(200)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

    with server(Target) as target, server(Admission) as admission:
        args = (target.server_port, admission.server_port, journal)
        with DurableCollector(*args, initialize=True) as c:
            assert c.observe()['state'] == 'COMMISSIONING'
            assert c.observe()['state'] == 'ARMED'
        backup(db, old)
        delay = 0.12
        with DurableCollector(*args) as c:
            c.observe()
            first = c.observe()
            assert first['state'] == ('UNKNOWN_BLOCKED' if lose_ack else 'LATCHED'), first
        with DurableCollector(*args) as c:
            c.observe()
            c.observe()
        assert counts['admission'] == 1, 'normal restart duplicated'
        backup(old, db)
        with DurableCollector(*args) as c:
            c.observe()
            c.observe()
        with closing(sqlite3.connect(ledger)) as c:
            distinct = c.execute('SELECT COUNT(DISTINCT identity), COUNT(DISTINCT run_id) FROM publications').fetchone()
        assert counts['admission'] == distinct[0] == distinct[1]
    return {'case': 'lost_ack_then_old_restore' if lose_ack else 'ack_then_old_restore', 'normal_restart': 'PASS', 'after_old_restore': 'PASS' if counts['admission'] == 1 else 'FAIL', 'http_health': counts['health'], 'http_admissions': counts['admission'], 'distinct_publications': distinct[0]}


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='v3-rollback-http-') as tmp:
        results = []
        for lose_ack in (False, True):
            root = Path(tmp) / str(lose_ack)
            root.mkdir(mode=0o700)
            results.append(campaign(root, lose_ack))
        passed = all(r['after_old_restore'] == 'PASS' for r in results)
        print(json.dumps({'classification': 'V3_COLLECTOR_ROLLBACK_HTTP_FIXTURE', 'result': 'PASS' if passed else 'FAIL', 'cases': results, 'production_authorized': False, 'limitations': ['Synthetic admission HTTP endpoint, not GAMMA/Core/Evidence', 'No process crash or production action']}, sort_keys=True))
        sys.exit(0 if passed else 1)
