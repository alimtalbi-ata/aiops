import ast
import pathlib
import unittest

SRC=pathlib.Path(__file__).resolve().parents[1]/'app/core/main.py'

class FakeHTTPException(Exception):
    def __init__(self,status_code,detail):
        self.status_code=status_code
        self.detail=detail

class FakeDB:
    def __init__(self,receipt):
        self.receipt=receipt
        self.queries=[]
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self,sql,params):
        self.queries.append(sql)
        if 'from aiops.runs' in sql:
            return FakeResult(('RUNNING',3,'DEMO'))
        if 'from aiops.command_receipts' in sql:
            return FakeResult(self.receipt)
        raise AssertionError('unexpected_write')

class FakeResult:
    def __init__(self,row): self.row=row
    def fetchone(self): return self.row

class CommandReceiptTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                and n.name=='command')
        fn.decorator_list=[]
        self.db=None
        ns={
            'db':lambda:self.db,
            'auth':lambda t:None,
            'bearer':lambda t:t,
            'HTTPException':FakeHTTPException,
            'Header':lambda **kw:None,
            'Command':object,
        }
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(SRC),'exec'),ns)
        self.command=ns['command']

    def run_command(self,rid='RUN-A',cmd='BLOCK'):
        x=type('Request',(),{
            'idempotency_key':'SAME-KEY',
            'command':cmd,
            'expected_version':3
        })()
        return self.command(rid,x)

    def test_same_operation_replays(self):
        self.db=FakeDB(('RUN-A','BLOCK',{'run_id':'RUN-A','version':4}))
        self.assertEqual(self.run_command()['version'],4)

    def test_other_run_rejected(self):
        self.db=FakeDB(('RUN-B','BLOCK',{'run_id':'RUN-B','version':4}))
        with self.assertRaises(FakeHTTPException) as ctx:
            self.run_command()
        self.assertEqual(ctx.exception.status_code,409)

    def test_other_command_rejected(self):
        self.db=FakeDB(('RUN-A','CANCEL',{'run_id':'RUN-A','version':4}))
        with self.assertRaises(FakeHTTPException) as ctx:
            self.run_command()
        self.assertEqual(ctx.exception.status_code,409)
