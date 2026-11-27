"""Actual rootless source-kit integration; synthetic target, no host action."""
from contextlib import contextmanager, closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'vertical'))
from collector_lab_config import SCOPE, private_file
from fenced_durable_collector import FencedDurableCollector
from continuous_collector import port
from rootless_preflight import source_daemon_preflight


def require(ok, message):
    if not ok:
        raise AssertionError(message)


class Target(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path != '/health':
            self.send_error(404)
            return
        time.sleep(self.server.delay)
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'OK')


class RecordingCollector(FencedDurableCollector):
    def publish(self, rows, correlation):
        self.test_rows = rows
        return super().publish(rows, correlation)


def request(gamma, route, token=None, data=None):
    origin = 'http://127.0.0.1:' + str(gamma)
    headers = {'Origin': origin}
    if token is not None:
        headers['Authorization'] = 'Bearer ' + token
    body = None
    if data is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(data, separators=(',', ':'), allow_nan=False).encode()
    with closing(http.client.HTTPConnection('127.0.0.1', gamma, timeout=30)) as conn:
        conn.request('POST' if data is not None else 'GET', route, body=body, headers=headers)
        res = conn.getresponse()
        raw = res.read(65537)
        require(len(raw) <= 65536 and res.headers.get('Cache-Control') == 'no-store', 'unverified response')
        return res.status, json.loads(raw)


def main():
    root = Path(os.environ.get('V3_ROOT', ''))
    require(os.getenv('GITHUB_ACTIONS') == 'true' and os.getuid() != 0
            and root == Path('/tmp/aiops-v3-rootless-ci') and root.resolve() == root,
            'disposable CI LAB required')
    source_daemon_preflight(root)
    env = dict(os.environ)
    env.pop('V3_DB_PASSWORD', None)
    env.pop('V3_LAB_TOKEN', None)
    project = 'aiops-v3-poc-' + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    compose = ['docker', 'compose', '--project-name', project, '--env-file',
               str(root / 'poc.env'), '-f', str(HERE / 'compose.poc-source.yml')]

    def sql(query):
        return subprocess.check_output(compose + ['exec', '-T', 'postgres', 'psql',
            '-v', 'ON_ERROR_STOP=1', '-U', 'aiops', '-d', 'aiops', '-Atc', query],
            env=env, text=True, timeout=30).strip()

    def counts():
        return tuple(map(int, sql('select (select count(*) from aiops.incidents),'
            '(select count(*) from aiops.runs),(select count(*) from aiops.evidence),'
            '(select count(*) from aiops.execution_receipts)').split('|')))

    def snapshot():
        return {table: sql("select count(*), md5(coalesce(string_agg(to_jsonb(t)::text,"
                           "'|' order by to_jsonb(t)::text), '')) from aiops." + table + " t")
                for table in ('incidents', 'runs', 'run_events', 'evidence', 'gates',
                              'command_receipts', 'execution_receipts')}

    launcher = [sys.executable, str(HERE / 'poc-gamma.py')]
    subprocess.run(launcher + ['--provision-collector'], env=env, check=True, timeout=60)
    token_file = root / 'collector-control' / 'collector.token'
    private_file(token_file)
    token = token_file.read_text().strip()
    journal = root / 'guarded-collector-journal'
    journal.mkdir(mode=0o700)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        gamma = port(sock.getsockname()[1])
    env['V3_GUARDED_GAMMA_PORT'] = str(gamma)

    @contextmanager
    def gamma_server(label):
        log = root / ('guarded-gamma-' + label + '.log')
        with log.open('x') as out:
            process = subprocess.Popen(launcher + ['--guarded-collector'], env=env,
                                       stdout=out, stderr=subprocess.STDOUT)
            try:
                for _ in range(60):
                    require(process.poll() is None, 'GAMMA exited before readiness')
                    if 'POC GAMMA: http://127.0.0.1:' + str(gamma) in log.read_text():
                        break
                    time.sleep(.5)
                else:
                    raise AssertionError('GAMMA readiness timeout')
                yield
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                        raise AssertionError('GAMMA failed bounded shutdown')

    observations = []
    before = counts()
    original = snapshot()
    with ThreadingHTTPServer(('127.0.0.1', 0), Target) as target:
        target.delay = .01
        thread = threading.Thread(target=target.serve_forever)
        thread.start()
        try:
            with gamma_server('initial'):
                with RecordingCollector(target.server_port, gamma, journal, scope=SCOPE,
                                        token=token, generation=0, initialize=True) as collector:
                    for _ in range(2):
                        observations.append(collector.observe())
                        time.sleep(1.1)
                    require(collector.state == 'ARMED', 'commissioning failed')
                    require(snapshot() == original, 'nominal windows wrote to PG')
                    target.delay = .12
                    for _ in range(2):
                        observations.append(collector.observe())
                        time.sleep(1.1)
                    require(collector.state == 'LATCHED' and observations[-1].get('published') is True,
                            'measured protected publication failed')
                    run_id = collector.run_id
                    rows = collector.test_rows
                    reference = collector.reconcile_reference()
                    require(reference['run_id'] == run_id, 'receipt mismatch')
                    expected = (before[0]+1, before[1]+1, before[2]+3, before[3])
                    require(counts() == expected, 'unexpected PG publication delta')
                    committed = snapshot()
                    for route in ('/api/v1/ingest/admit', '/api/v1/ingest/create',
                                  '/api/v1/ingest/persist', '/api/v1/enterprise-clock/advance'):
                        require(request(gamma, route, token, rows)[0] == 403, 'legacy bypass accepted')
                    require(request(gamma, '/api/v1/collector/admit', token,
                                    {'generation': 0, 'rows': rows})[0] == 403, 'replay accepted')
                    require(snapshot() == committed, 'refused request mutated PG')
            with gamma_server('restart'):
                with FencedDurableCollector(target.server_port, gamma, journal, scope=SCOPE,
                                            token=token, generation=0) as collector:
                    require(collector.state == 'LATCHED' and collector.run_id == run_id,
                            'collector restart lost state')
                    require(collector.reconcile_reference() == reference, 'restart receipt changed')
                    for delay in (.01, .01, .12, .12):
                        target.delay = delay
                        observations.append(collector.observe())
                        require(collector.state == 'LATCHED' and not observations[-1].get('published'),
                                'unexpected restart publication or local rearm')
                    status, result = request(gamma, '/api/v1/incident-context/dynamic?run_id=' + run_id)
                    require(status == 200 and result['context']['policy'] == 'DENY'
                            and len(result['context']['evidence']) == 3
                            and result['production_authorized'] is False, 'GAMMA readback mismatch')
                    require(snapshot() == committed and counts() == expected, 'restart mutated PG')
        finally:
            target.shutdown()
            thread.join(5)
            require(not thread.is_alive(), 'target thread leaked')
    report = {'classification': 'SYNTHETIC_GUARDED_COLLECTOR_SOURCE_LAB', 'result': 'PASS',
              'run_id': run_id, 'receipt': reference, 'pg_before': before, 'pg_after': expected,
              'nominal_no_write': True, 'legacy_and_replay_denied': True,
              'restart_receipt_exact': True, 'pg_snapshot_unchanged_after_commit': True,
              'observations': observations, 'rearm': 'NOT_RUN', 'physical_dr': 'NOT_RUN',
              'production_authorized': False}
    with (root / 'guarded-collector-report.json').open('x') as out:
        json.dump(report, out, sort_keys=True)
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
