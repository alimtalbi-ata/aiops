"""Regression for psycopg 3 Connection.execute() returning a cursor."""
import importlib.util
import os
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
os.environ.setdefault('AIOPS_INTERNAL_TOKEN','unit-only-token')
os.environ.setdefault('DATABASE_URL','postgresql://unit:unit@localhost:5432/unit')
SPEC=importlib.util.spec_from_file_location('aiops_core_stage',ROOT/'app'/'core'/'main.py')
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class FakeCursor:
    def __init__(self,row): self.row=row
    def fetchone(self): return self.row

class FakeConnection:
    def __init__(self,row): self.row=row;self.calls=[]
    def execute(self,sql,params):
        self.calls.append((sql,params))
        return FakeCursor(self.row)
    # Deliberately no fetchone method: psycopg.Connection does not expose it.

class StagePersistenceTests(unittest.TestCase):
    def test_reuses_previous_attempt_using_cursor(self):
        conn=FakeConnection((4,))
        MOD.set_stage(conn,'RUN-1','NORMALIZE','PASS')
        self.assertEqual(len(conn.calls),2)
        self.assertEqual(conn.calls[1][1][3],4)

    def test_missing_previous_stage_defaults_to_zero(self):
        conn=FakeConnection(None)
        MOD.set_stage(conn,'RUN-2','CORRELATE','RUNNING')
        self.assertEqual(conn.calls[1][1][3],0)

    def test_explicit_attempt_does_not_read_cursor(self):
        conn=FakeConnection(None)
        MOD.set_stage(conn,'RUN-3','POLICY','BLOCKED',attempt=2)
        self.assertEqual(len(conn.calls),1)
        self.assertEqual(conn.calls[0][1][3],2)

if __name__=='__main__': unittest.main()
