"""Actual capture CLI must reject topology nodes without an auditable identity."""
import json
import unittest

import test_fs147_capture_json_admission as capture_cli


class NodeIdentityTests(unittest.TestCase):
    run_capture = capture_cli.CaptureJsonAdmissionTests.run_capture
    valid_capture = capture_cli.CaptureJsonAdmissionTests.valid_capture

    def test_invalid_node_identity_holds(self):
        for node_id in ('', '   ', None, 17, True):
            with self.subTest(node_id=node_id):
                data = json.loads(self.valid_capture())
                old = data['graph']['nodes'][0]['node_id']
                data['graph']['nodes'][0]['node_id'] = node_id
                for edge in data['graph']['edges']:
                    for key in ('source_id', 'target_id'):
                        if edge[key] == old:
                            edge[key] = node_id
                for fact in data['fs_facts']['facts']:
                    if fact['node_id'] == old:
                        fact['node_id'] = node_id
                        value = fact['value']
                        if isinstance(value, str):
                            value = json.loads(value)
                        value['target_node_id'] = node_id
                        fact['value'] = value
                result = self.run_capture(json.dumps(data))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(json.loads(result.stdout)['status'], 'HOLD')
                self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
