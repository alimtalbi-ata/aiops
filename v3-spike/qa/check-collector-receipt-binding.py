"""Synthetic negative receipt binding test; HTTP real, measurements mocked."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vertical'))
import continuous_collector as collector


def campaign(kind):
    seen = []

    class Admission(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            assert self.path == '/api/v1/ingest/admit'
            rows = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert len(rows) == 3 and all(r['synthetic'] is True for r in rows)
            seen.extend(r['id'] for r in rows)
            evidence = {'empty': [{}, {}, {}],
                        'unrelated': [{'id': 'unrelated-' + str(i), 'tenant': 'other-synthetic'} for i in range(3)],
                        'wrong_count': [{}, {}]}[kind]
            response = {'admission': {'classification': 'SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1',
                        'admitted': True, 'operational_decision': 'DENY', 'production_authorized': False},
                        'publication': {'core': {'run': {'run_id': 'RUN-0000000000000001', 'mode': 'DEMO',
                        'status': 'CREATED'}}, 'stored_evidence': evidence}, 'production_authorized': False}
            self.send_response(200)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

    with HTTPServer(('127.0.0.1', 0), Admission) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            target = 1024 if server.server_port != 1024 else 1025  # never contacted
            windows = [{'at': '2026-11-27T00:00:00Z', 'median': value, 'samples': [value] * 5}
                       for value in (10, 10, 100, 100)]
            with patch.object(collector, 'sample', side_effect=windows):
                c = collector.Collector(target, server.server_port)
                results = [c.observe() for _ in windows]
            assert results[1]['state'] == 'ARMED' and len(seen) == 3
            return {'case': kind, 'state': c.state, 'published': results[-1].get('published', False),
                    'run_id': c.run_id, 'pass': c.state == 'UNKNOWN_BLOCKED' and c.run_id is None}
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    results = [campaign(kind) for kind in ('empty', 'unrelated', 'wrong_count')]
    print(json.dumps({'classification': 'SYNTHETIC_HTTP_NEGATIVE_RECEIPT', 'cases': results,
                      'production_authorized': False}, sort_keys=True))
    sys.exit(0 if all(case['pass'] for case in results) else 1)
