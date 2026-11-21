import ast
import pathlib
import unittest

SRC=pathlib.Path(__file__).resolve().parents[1]/'app/worker/main.py'

class StageRetryTests(unittest.TestCase):
    def test_started_event_is_retry_stable(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body
                if isinstance(n,ast.FunctionDef)
                and n.name=='_execute_stage_blocking')
        started=next(n for n in ast.walk(fn)
                if isinstance(n,ast.Dict)
                and any(isinstance(k,ast.Constant)
                        and k.value=='event_type'
                        for k in n.keys))
        payload=ast.literal_eval(next(
            v for k,v in zip(started.keys,started.values)
            if isinstance(k,ast.Constant) and k.value=='payload'
        ))
        self.assertNotIn('attempt',payload)
        self.assertTrue(payload['retry_stable'])
