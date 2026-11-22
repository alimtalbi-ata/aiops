import ast
import pathlib
import unittest

SRC=pathlib.Path(__file__).resolve().parents[1]/'app/worker/main.py'

class EarlyRecoveryTests(unittest.TestCase):
    def test_recovery_precedes_stage_started(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                and n.name=='_execute_stage_blocking')
        source=ast.get_source_segment(SRC.read_text(),fn)
        recovery=source.index('recover_committed_critic_block(rid)')
        started=source.index("event_type':'STAGE_STARTED'")
        self.assertLess(recovery,started)

    def test_recovery_returns_before_stage_execution(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                and n.name=='_execute_stage_blocking')
        conditional=next(
            n for n in fn.body
            if isinstance(n,ast.If)
            and isinstance(n.test,ast.Compare)
            and ast.unparse(n.test)=="stage == 'DGX_CRITIC'"
        )
        self.assertTrue(any(
            isinstance(n,ast.Return)
            for n in ast.walk(conditional)
        ))
