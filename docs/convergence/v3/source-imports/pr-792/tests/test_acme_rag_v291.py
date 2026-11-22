import unittest
from pathlib import Path

class ACMERagTests(unittest.TestCase):
    def test_documents_scoped_and_labeled(self):
        source=(Path(__file__).resolve().parents[1]/'app/copilot/acme_knowledge.py').read_text()
        self.assertIn('ACME-RB-SAN-001',source)
        self.assertIn('DEMO_REFERENCE',source)
        self.assertIn('ci_id not in d["ci_ids"]',source)

if __name__=='__main__':
    unittest.main()
