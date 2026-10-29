import ast,unittest
from pathlib import Path
SOURCE=(Path(__file__).resolve().parents[1]/"app/portal/main.py").read_text()
class StoryPageTests(unittest.TestCase):
    def test_story_route_present(self):
        tree=ast.parse(SOURCE)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="policy_story")
        self.assertTrue(fn)
    def test_explicit_no_write_contract(self):
        segment=SOURCE.split('def policy_story():',1)[1]
        self.assertIn("FICTIF / SANS EFFET",segment)
        self.assertIn('aucune API d\'écriture',segment)
        self.assertNotIn('post_json(',segment)
        self.assertNotIn('fetch(',segment)
    def test_story_has_stop_and_rejection(self):
        segment=SOURCE.split('def policy_story():',1)[1]
        self.assertIn("STOP_AUTO",segment)
        self.assertIn("Exécution refusée",segment)
if __name__=="__main__":unittest.main()
