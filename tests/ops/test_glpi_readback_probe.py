"""Offline native-GET contract tests; no GLPI service contacted."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('probe', ROOT/'scripts/ops/glpi_readback_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
RUN = 'RUN-8CA56A39E58944F1'
INC = 'INC-FS1250-AUTOGLPI-625916362ACD42C9'

class ReadbackTests(unittest.TestCase):
    def inspect(self, **changes):
        payload = dict(id=201, name=RUN, content=INC, is_deleted=0)
        payload.update(changes)
        with patch.object(probe, 'glpi_get', return_value=(200, payload)) as get:
            result = probe.inspect_ticket(201, RUN, INC, 'https://glpi.invalid', 'test-token')
        get.assert_called_once_with('https://glpi.invalid', 'Ticket/201', 'test-token', None)
        return result

    def test_exact_triplet(self):
        self.assertEqual(self.inspect()['readback'], 'MATCHED_MARKER')

    def test_foreign_or_missing_ticket_identity(self):
        for value in (202, None, True, '201'):
            with self.subTest(value=value):
                self.assertEqual(self.inspect(id=value)['readback'], 'MISMATCH')

    def test_substring_markers_and_missing_incident_refused(self):
        for changes in ({'name':RUN+'A'}, {'name':'X'+RUN}, {'name':RUN+'-OTHER'},
                        {'content':INC+'A'}, {'content':''}, {'is_deleted':1}):
            with self.subTest(changes=changes):
                self.assertEqual(self.inspect(**changes)['readback'], 'MISMATCH')

    def test_http_errors_do_not_verify(self):
        for status in (401, 403, 404, 500):
            with patch.object(probe, 'glpi_get', return_value=(status, {})):
                self.assertNotEqual(probe.inspect_ticket(201,RUN,INC,'','')['readback'], 'MATCHED_MARKER')

    def test_native_request_is_get_only(self):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"id":201}'
        response.__enter__.return_value = response
        with patch.object(probe.urllib.request, 'urlopen', return_value=response) as open_url:
            probe.glpi_get('https://glpi.invalid', 'Ticket/201', 'test-token')
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertIsNone(request.data)
        self.assertEqual(request.full_url, 'https://glpi.invalid/apirest.php/Ticket/201')

if __name__ == '__main__':
    unittest.main()
