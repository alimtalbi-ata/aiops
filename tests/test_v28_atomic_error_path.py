import ast
import pathlib
import unittest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"app/worker/main.py"

class AtomicErrorPathTests(unittest.TestCase):
    def test_atomic_error_does_not_use_intelligence_fallback(self):
        tree=ast.parse(SOURCE.read_text())
        fn=next(n for n in ast.walk(tree)
                if isinstance(n,ast.FunctionDef)
                and n.name=="_execute_stage_blocking")

        handlers=[
            n for n in ast.walk(fn)
            if isinstance(n,ast.ExceptHandler)
        ]
        atomic=[
            h for h in handlers
            if isinstance(h.type,ast.Name)
            and h.type.id=="AtomicDenialBlockError"
        ]
        self.assertEqual(len(atomic),1)
        self.assertTrue(any(
            isinstance(n,ast.Raise)
            for n in ast.walk(atomic[0])
        ))

        source=ast.get_source_segment(SOURCE.read_text(),fn)
        self.assertIn("atomic_denial_block_unconfirmed",source)
        self.assertIn("critic-denial-resume",source)
        self.assertIn("except AtomicDenialBlockError:",source)
        self.assertIn("atomic_denial_block_unconfirmed",source)

if __name__=="__main__":
    unittest.main()
