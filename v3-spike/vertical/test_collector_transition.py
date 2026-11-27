"""HTTP receipt boundary; real Collector, synthetic admission and measurements."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import unittest
from unittest.mock import patch

import continuous_collector as collector
from collector_receipt import digest
from ingestion_demo import ingest


def response_for(rows):
    correlation = ingest(rows)
    incident = correlation['incidents'][0]
    signals = incident['evidence']
    batch = digest(incident)
    run = {'run_id': 'RUN-0000000000000001', 'incident_id': 'INC-CI-INGEST-' + batch[:32],
           'mode': 'DEMO', 'status': 'CREATED'}
    receipts = [{'evidence_id': 'EVID-' + str(i), 'payload_hash': digest({'run_id': run['run_id'],
                 'incident_id': run['incident_id'], 'signal': s, 'correlation_id': incident['id'],
                 'resource': incident['resource']})} for i, s in enumerate(signals)]
    return {'production_authorized': False, 'admission': {'production_authorized': False,
            'admitted': True, 'classification': 'SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1',
            'operational_decision': 'DENY', 'batch_sha256': batch, 'resource': incident['resource'],
            'references': [{'event_id': s['event_id'], 'sha256': s['sha256']} for s in signals]},
            'publication': {'production_authorized': False, 'correlation': correlation,
            'core': {'classification': 'SYNTHETIC_CANONICAL_RUN', 'production_authorized': False,
                     'policy': 'DENY', 'run': run}, 'stored_evidence': receipts}}


class TransitionTests(unittest.TestCase):
    def test_receipt_transition(self):
        for kind in ('valid', 'empty', 'foreign', 'replay', 'wrong_count', 'lost_ack'):
            with self.subTest(kind=kind):
                requests = []
                windows = [{'at': '2026-11-27T00:00:%02dZ' % i, 'median': value, 'samples': [value] * 5}
                           for i, value in enumerate((10, 10, 100, 100, 100, 100))]
                old = response_for(collector.batch(windows[0], windows[2]))

                class Admission(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_POST(self):
                        rows = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                        requests.append(rows)
                        response = response_for(rows)
                        if kind == 'lost_ack':
                            self.close_connection = True
                            return
                        if kind == 'empty':
                            response['publication']['stored_evidence'] = [{}, {}, {}]
                        elif kind == 'foreign':
                            response['publication']['stored_evidence'][0]['payload_hash'] = '0' * 64
                        elif kind == 'replay':
                            response = old
                        elif kind == 'wrong_count':
                            response['publication']['stored_evidence'].pop()
                        self.send_response(200)
                        self.send_header('Cache-Control', 'no-store')
                        self.end_headers()
                        self.wfile.write(json.dumps(response).encode())

                with HTTPServer(('127.0.0.1', 0), Admission) as server:
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        target = 1024 if server.server_port != 1024 else 1025  # mocked, never contacted
                        with patch.object(collector, 'sample', side_effect=windows):
                            c = collector.Collector(target, server.server_port)
                            results = [c.observe() for _ in windows]
                        self.assertEqual(len(requests), 1)
                        self.assertEqual(results[1]['state'], 'ARMED')
                        if kind == 'valid':
                            self.assertTrue(results[3]['published'])
                            self.assertEqual(c.run_id, 'RUN-0000000000000001')
                            self.assertEqual(c.state, 'LATCHED')
                        else:
                            self.assertTrue(results[3]['publication_unknown'])
                            self.assertEqual(c.state, 'UNKNOWN_BLOCKED')
                            self.assertIsNone(c.run_id)
                        self.assertFalse(any(row.get('published') for row in results[4:]))
                    finally:
                        server.shutdown()
                        thread.join()


if __name__ == '__main__':
    unittest.main()
