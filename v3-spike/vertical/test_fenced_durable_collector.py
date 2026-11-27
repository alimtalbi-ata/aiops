"""Real loopback HTTP and collector SQLite; synthetic publisher/Twin, no remediation."""
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError

from collector_admission_fence import initialize, provision
from collector_admission_service import publish, lookup
from durable_collector import DurableCollector
from fenced_durable_collector import FencedDurableCollector
from test_collector_admission_service import GraphFixture
from test_collector_transition import response_for


@contextmanager
def serve(handler):
    with HTTPServer(('127.0.0.1', 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join()


def backup(source, destination):
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)
    destination.chmod(0o600)


class FencedCollectorTests(unittest.TestCase):
    def test_restart_ack_and_old_armed_snapshot(self):
        for fault in ('none', 'lost_ack', 'publisher_failure'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                journal = root / 'journal'
                journal.mkdir(mode=0o700)
                authority = root / 'authority.db'
                old = root / 'old.db'
                scope = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-one')
                token = secrets.token_hex(32)
                with closing(sqlite3.connect(authority)) as db:
                    initialize(db)
                    provision(db, scope, token)
                counts = {'health': 0, 'admit': 0, 'lookup': 0, 'publisher': 0}
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

                def publisher(rows):
                    counts['publisher'] += 1
                    with closing(sqlite3.connect(journal / 'collector.sqlite3')) as db:
                        saved = json.loads(db.execute('SELECT payload FROM state').fetchone()[0])
                    self.assertEqual(saved['state'], 'UNKNOWN_BLOCKED')
                    self.assertEqual(saved['fence']['pending']['episode'], rows[0]['id'][:32])
                    self.assertNotIn(token, json.dumps(saved))
                    if fault == 'publisher_failure':
                        raise OSError('synthetic publisher unavailable')
                    return response_for(rows)['publication']

                class Admission(Quiet):
                    def do_POST(self):
                        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                        try:
                            with closing(sqlite3.connect(authority)) as db:
                                args = dict(scope=scope, authorization=self.headers.get('Authorization'), generation=data['generation'])
                                if self.path == '/api/v1/collector/admit':
                                    counts['admit'] += 1
                                    result = publish(db, **args, rows=data['rows'], graph=GraphFixture(), publish_records=publisher)
                                    if fault == 'lost_ack':
                                        self.close_connection = True
                                        return
                                elif self.path == '/api/v1/collector/receipt':
                                    counts['lookup'] += 1
                                    result = lookup(db, **args, episode=data['episode'], batch=data['batch'])
                                else:
                                    raise ValueError('unknown route')
                            status = 200
                        except Exception:
                            status, result = 409, {'state': 'UNKNOWN_BLOCKED'}
                        self.send_response(status)
                        self.send_header('Cache-Control', 'no-store')
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())

                with serve(Target) as target, serve(Admission) as admission:
                    args = (target.server_port, admission.server_port, journal)
                    config = dict(scope=scope, token=token, generation=0)
                    with FencedDurableCollector(*args, **config, initialize=True) as c:
                        c.observe()
                        self.assertEqual(c.observe()['state'], 'ARMED')
                    backup(journal / 'collector.sqlite3', old)
                    delay = .12
                    with FencedDurableCollector(*args, **config) as c:
                        c.observe()
                        state = c.observe()['state']
                        self.assertEqual(state, 'LATCHED' if fault == 'none' else 'UNKNOWN_BLOCKED')
                        saved = c.pending.copy()
                    with FencedDurableCollector(*args, **config) as c:
                        self.assertEqual(c.pending, saved)
                        reference = c.reconcile_reference()
                        self.assertEqual(reference['state'], 'UNKNOWN_BLOCKED' if fault == 'publisher_failure' else 'COMMITTED')
                        self.assertEqual(c.state, state)
                        # Healthy windows are test setup only, not a remediation claim.
                        delay = .01
                        c.observe()
                        self.assertEqual(c.observe()['state'], state)
                    self.assertEqual(counts['admit'], 1)
                    with self.assertRaises(ValueError):
                        FencedDurableCollector(*args, **(config | {'generation': 1}))
                    with self.assertRaises(ValueError):
                        FencedDurableCollector(*args, **(config | {'scope': ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-other')}))
                    backup(old, journal / 'collector.sqlite3')
                    delay = .12
                    with FencedDurableCollector(*args, **config) as c:
                        c.observe()
                        self.assertEqual(c.observe()['state'], 'UNKNOWN_BLOCKED')
                        self.assertNotEqual(c.pending['episode'], saved['episode'])
                        with self.assertRaises(HTTPError):
                            c.reconcile_reference()
                    self.assertEqual(counts, {'health': 40, 'admit': 2, 'lookup': 2, 'publisher': 1})

    def test_legacy_journal_is_not_implicitly_upgraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with DurableCollector(1024, 1025, root, initialize=True):
                pass
            with self.assertRaises(ValueError):
                FencedDurableCollector(1024, 1025, root, scope=('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-one'),
                                       token=secrets.token_hex(32), generation=0)
            with DurableCollector(1024, 1025, root) as c:
                self.assertEqual(c.state, 'COMMISSIONING')


if __name__ == '__main__':
    unittest.main()
