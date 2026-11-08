"""Synthetic offline receipts never establish authenticated GLPI evidence."""
import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy
from unittest.mock import patch
import json
import tempfile

p = Path(__file__).resolve().parents[2]/'scripts/ops/itsm_link_diagnosis.py'
s = importlib.util.spec_from_file_location('itsm', p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
RUN = 'RUN-8CA56A39E58944F1'
INC = 'INC-FS1250-AUTOGLPI-625916362ACD42C9'


def identity():
    return dict(run_id=RUN, incident_id=INC, tenant_id='tenant-a', glpi_instance_id='glpi-a')


def sample():
    a = identity()
    a.update(database=dict(run=identity(), glpi_links=[], itsm_xref=[]),
             checks=dict(glpi_core_link='PASS'), external_glpi_observation=dict(ticket_id=201))
    return a


def confirmed():
    a = sample()
    a['database']['glpi_links'] = [dict(identity(), glpi_ticket_id=201, state='CONFIRMED')]
    a['database']['itsm_xref'] = [dict(identity(), ticket_id=201, glpi_ticket_readback_verified=True)]
    return a


def readback():
    return dict(identity(), ticket=dict(ticket_id=201, http=200, readback='MATCHED_MARKER',
                ticket_id_verified=True, ticket_active=True,
                run_marker_present=True, incident_marker_present=True))


class DiagnosisTests(unittest.TestCase):
    def hold(self, a, rb=None, cause=None):
        result = m.diagnose(a, rb)
        self.assertEqual(result['verdict'], 'HOLD')
        self.assertNotEqual(result['cause'], 'LINK_VERIFIED')
        if cause:
            self.assertEqual(result['cause'], cause)
        return result

    def test_absent_link_is_not_missing_ticket(self):
        self.hold(sample(), cause='CORE_LINK_ABSENT_GLPI_UNVERIFIED')

    def test_marker_claim_without_link_is_not_pass(self):
        self.hold(sample(), readback(), 'GLPI_MARKERS_MATCH_CORE_LINK_ABSENT')

    def test_database_boolean_alone_never_verifies(self):
        self.hold(confirmed(), cause='LINK_CONSISTENT_UNATTESTED')

    def test_consistent_json_receipts_still_do_not_authenticate_glpi(self):
        self.hold(confirmed(), readback(), 'LINK_CONSISTENT_UNATTESTED')

    def test_forged_authentication_flags_do_not_enable_pass(self):
        rb = readback()
        rb.update(authenticated=True, signature_verified=True, provenance='AUTHENTICATED_SOURCE_API')
        self.hold(confirmed(), rb, 'LINK_CONSISTENT_UNATTESTED')

    def test_legacy_incident_only_rows_remain_unverified(self):
        a = confirmed()
        for x in a['database']['itsm_xref']:
            del x['run_id']
        self.hold(a, cause='IDENTITY_UNVERIFIED')

    def test_missing_scope_is_not_assumed(self):
        for field in ('tenant_id', 'glpi_instance_id'):
            for group in ('glpi_links', 'itsm_xref'):
                with self.subTest(field=field, group=group):
                    a = confirmed()
                    del a['database'][group][0][field]
                    self.hold(a, cause='IDENTITY_UNVERIFIED')

    def test_core_run_mismatch_or_missing(self):
        for value in ('RUN-FOREIGN', None, ''):
            a = confirmed()
            a['database']['run']['run_id'] = value
            self.hold(a, cause='IDENTITY_MISMATCH')

    def test_foreign_xref_run_ticket_incident_tenant_instance(self):
        for field, value in (('run_id','RUN-FOREIGN'), ('ticket_id',202),
                             ('incident_id','INC-FOREIGN'), ('tenant_id','tenant-b'),
                             ('glpi_instance_id','glpi-b')):
            with self.subTest(field=field):
                a = confirmed()
                a['database']['itsm_xref'][0][field] = value
                self.hold(a, readback(), 'IDENTITY_MISMATCH')

    def test_foreign_link_run_incident_tenant_instance(self):
        for field in ('run_id','incident_id','tenant_id','glpi_instance_id'):
            a = confirmed()
            a['database']['glpi_links'][0][field] = 'foreign'
            self.hold(a, readback(), 'IDENTITY_MISMATCH')

    def test_readback_envelope_foreign_identity(self):
        for field in ('run_id','incident_id','tenant_id','glpi_instance_id'):
            rb = readback()
            rb[field] = 'foreign'
            self.hold(confirmed(), rb, 'IDENTITY_MISMATCH')

    def test_readback_foreign_ticket(self):
        rb = readback()
        rb['ticket']['ticket_id'] = 202
        self.hold(confirmed(), rb, 'IDENTITY_MISMATCH')

    def test_ticket_body_cannot_contradict_envelope(self):
        for field in ('run_id','incident_id','tenant_id','glpi_instance_id'):
            rb = readback()
            rb['ticket'][field] = 'foreign'
            self.hold(confirmed(), rb, 'IDENTITY_MISMATCH')

    def test_duplicate_xrefs_are_ambiguous_even_identical(self):
        a = confirmed()
        a['database']['itsm_xref'] *= 2
        self.hold(a, readback(), 'AMBIGUOUS_XREFS')

    def test_concurrent_or_contradictory_xrefs_never_select_a_good_row(self):
        for field, value in (('run_id','RUN-FOREIGN'), ('ticket_id',202),
                             ('tenant_id','tenant-b'), ('glpi_instance_id','glpi-b'),
                             ('glpi_ticket_readback_verified',False), ('event_type','REVOKED')):
            a = confirmed()
            other = dict(a['database']['itsm_xref'][0], **{field:value})
            a['database']['itsm_xref'].append(other)
            self.hold(a, readback(), 'AMBIGUOUS_XREFS')
            a['database']['itsm_xref'].reverse()
            self.hold(a, readback(), 'AMBIGUOUS_XREFS')

    def test_single_revoked_or_negative_xref_is_not_a_consistent_link(self):
        for field, value in (("event_type", "REVOKED"),
                             ("glpi_ticket_readback_verified", False),
                             ("core_run_readback_verified", False)):
            a = confirmed()
            a['database']['itsm_xref'][0][field] = value
            self.hold(a, readback(), 'XREF_CONTRADICTORY')

    def test_multiple_links_are_not_collapsed(self):
        for tid in (201,202):
            a = confirmed()
            a['database']['glpi_links'].append(dict(identity(), glpi_ticket_id=tid, state='CONFIRMED'))
            self.hold(a, cause='AMBIGUOUS_TICKET_LINKS')

    def test_different_ticket_link_is_preserved(self):
        a = sample()
        a['database']['glpi_links'] = [dict(identity(), glpi_ticket_id=202, state='CONFIRMED')]
        self.hold(a, cause='DIFFERENT_TICKET_LINKED')

    def test_xref_without_link(self):
        a = confirmed()
        a['database']['glpi_links'] = []
        self.hold(a, cause='XREF_WITHOUT_CORE_LINK')

    def test_no_run(self):
        a = sample()
        a['database']['run'] = None
        self.hold(a, cause='CORE_RUN_MISSING')

    def test_auth_required(self):
        rb = dict(identity(), ticket=dict(ticket_id=201, readback='AUTH_REQUIRED', http=401))
        self.hold(confirmed(), rb, 'GLPI_READBACK_AUTH_REQUIRED')

    def test_incomplete_marker_claim(self):
        for field in ('ticket_id_verified','ticket_active','run_marker_present','incident_marker_present'):
            rb = readback()
            rb['ticket'][field] = False
            self.hold(confirmed(), rb, 'GLPI_TICKET_IDENTITY_MISMATCH')

    def test_invalid_ticket_values(self):
        for value in (None, True, False, 0, -1, 201.0, '0201', '201 ', [], {}):
            a = sample()
            a['external_glpi_observation']['ticket_id'] = value
            self.hold(a, cause='TICKET_ID_NOT_PROVIDED')

    def test_malformed_reports_fail_closed(self):
        for value in (None, [], 'bad', {}):
            self.hold(value)
        for field in ('glpi_links', 'itsm_xref'):
            for value in (None, {}, [None], ['bad']):
                a = sample()
                a['database'][field] = value
                self.hold(a, cause='MALFORMED_REPORT')
        self.hold(sample(), [], 'MALFORMED_REPORT')

    def test_44_synthetic_links_replay_without_mutation_or_api_proof(self):
        fixtures = []
        for n in range(44):
            a = confirmed()
            a['external_glpi_observation']['ticket_id'] = 156+n
            a['database']['glpi_links'][0]['glpi_ticket_id'] = 156+n
            a['database']['itsm_xref'][0]['ticket_id'] = 156+n
            fixtures.append(a)
        before = deepcopy(fixtures)
        for a in fixtures:
            self.assertEqual(self.hold(a), self.hold(a))
        self.assertEqual(fixtures, before)

    def test_cli_returns_hold_exit_code_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/'source.json', Path(tmp)/'out.json'
            source.write_text(json.dumps(confirmed()))
            before = source.read_bytes()
            with patch('sys.argv', ['diagnosis', '--linkage', str(source), '--output', str(output)]):
                self.assertEqual(m.main(), 2)
            self.assertEqual(json.loads(output.read_text())['verdict'], 'HOLD')
            self.assertEqual(source.read_bytes(), before)

if __name__ == '__main__':
    unittest.main()
