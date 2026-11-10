import ast
from contextlib import contextmanager
from pathlib import Path
import unittest

class HTTPException(Exception):
    def __init__(self,status_code,detail): self.status_code=status_code

class Cursor:
    def __init__(self,winner): self.winner=winner; self.calls=[]
    def execute(self,sql,params): self.calls.append((sql,params)); return self
    def fetchone(self): return ('RUN-1',) if self.winner else None

class CheckpointMonotonicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Path(__file__).resolve().parents[1]/'app/core/main.py'
        f=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='checkpoint')
        f.decorator_list=[]
        cls.code=compile(ast.Module(body=[f],type_ignores=[]),str(p),'exec')
    def invoke(self,payload,winner=True):
        cursor=Cursor(winner)
        @contextmanager
        def db(): yield cursor
        ns={'db':db,'auth':lambda x:None,'bearer':lambda x:x,'Header':lambda default=None:default,'HTTPException':HTTPException}
        exec(self.code,ns)
        try: return ns['checkpoint']('RUN-1',payload),None,cursor
        except HTTPException as e: return None,e.status_code,cursor
    def test_sql_atomic_fencing(self):
        result,error,c=self.invoke({'stage':'POLICY','version':2,'workflow_id':'RUN-1'})
        self.assertIsNone(error)
        self.assertEqual(result['version'],2)
        sql,params=c.calls[0]
        for clause in ('on conflict(run_id)','version < excluded.version','stage = excluded.stage','workflow_id = excluded.run_id','returning run_id'):
            self.assertIn(clause,sql)
        self.assertEqual(params,('RUN-1','POLICY',2,'RUN-1'))
    def test_stale_conflict_fails_closed(self):
        _,error,c=self.invoke({'stage':'POLICY','version':2},False)
        self.assertEqual(error,409)
        self.assertEqual(len(c.calls),1)
    def test_bad_versions_no_write(self):
        for version in (None,True,False,-1,'2',1.5,[],{}):
            with self.subTest(version=version):
                _,error,c=self.invoke({'stage':'POLICY','version':version})
                self.assertEqual(error,422)
                self.assertFalse(c.calls)
    def test_bad_stage_no_write(self):
        for stage in (None,'','  ',1):
            _,error,c=self.invoke({'stage':stage,'version':1})
            self.assertEqual(error,422)
            self.assertFalse(c.calls)
    def test_foreign_workflow_no_write(self):
        _,error,c=self.invoke({'stage':'POLICY','version':1,'workflow_id':'RUN-2'})
        self.assertEqual(error,409)
        self.assertFalse(c.calls)
if __name__=='__main__': unittest.main()
