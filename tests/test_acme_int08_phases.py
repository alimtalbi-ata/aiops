import unittest
from portal.acme_runtime_context import digest
from portal.acme_int08_phases import admission_v1,preterminal_v1

class PhaseRefusals(unittest.TestCase):
    def test_missing(self):
        a=admission_v1({}, {}, None, None, {k:k+'-source' for k in ('core','twin','policy','critic','hitl')},{},as_of_utc='2026-11-18T09:00:00Z')
        self.assertEqual(a['qualification'],'BLOCK')
        self.assertEqual(a['contract_status'],'UNQUALIFIED')
    def test_bad_registry(self):
        a=admission_v1({}, {}, {}, {}, {}, {},as_of_utc='2026-11-18T09:00:00Z')
        self.assertEqual(a['qualification'],'REJECT')
    def test_preterminal_no_forged_verdict(self):
        r=preterminal_v1({}, {}, {'contract_status':'CONTRACT_ONLY'}, {}, {}, {}, {}, {},as_of_utc='2026-11-18T09:00:00Z')
        self.assertEqual(r['qualification'],'REJECT')
        for k in ('runtime_attested','execution_allowed','finish_authorized','resolution_authorized','live_remediation_authorized'):
            self.assertIs(r[k],False)
