import os
import pathlib
import subprocess
import tempfile
import unittest
import json

SCRIPT = pathlib.Path(__file__).with_name('synthetic-e2e.sh')

class Regression(unittest.TestCase):
    def check_case(self, rows, expected, unavailable=False, optimize='0'):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            curl = p / 'curl'
            curl.write_text('''#!/usr/bin/env python3
import os,sys
url=sys.argv[-1]
if url.endswith('/health'): print('{}')
elif url.endswith('/api/demo'): print('{"run_id":"qa-123"}')
elif os.environ['UNAVAILABLE']=='1': sys.exit(22)
else: print(os.environ['BOOTSTRAP'])
''')
            curl.chmod(0o755)
            env = dict(os.environ, PATH=tmp+os.pathsep+os.environ['PATH'], E2E_ATTEMPTS='1', BASE_URL='http://fixture.invalid', BOOTSTRAP=json.dumps({'runs':{'items':rows}}), UNAVAILABLE=str(int(unavailable)), PYTHONOPTIMIZE=optimize)
            r = subprocess.run(['bash',str(SCRIPT)],env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode == 0, expected, r.stdout+r.stderr)
            self.assertEqual('SYNTHETIC_E2E=PASS' in r.stdout, expected)
    def test_timeout(self): self.check_case([],False)
    def test_wrong_id(self): self.check_case([{'run_id':'qa-1234','status':'RESOLVED'}],False)
    def test_failed(self): self.check_case([{'run_id':'qa-123','status':'FAILED'}],False)
    def test_success(self): self.check_case([{'run_id':'qa-123','status':'RESOLVED'}],True)
    def test_duplicate(self): self.check_case([{'run_id':'qa-123','status':'RESOLVED'}]*2,False)
    def test_duplicate_optimized(self): self.check_case([{'run_id':'qa-123','status':'RESOLVED'}]*2,False,optimize='1')
    def test_success_optimized(self): self.check_case([{'run_id':'qa-123','status':'RESOLVED'}],True,optimize='1')
    def test_invalid_status_optimized(self): self.check_case([{'run_id':'qa-123','status':['RESOLVED']}],False,optimize='1')
    def test_unavailable(self): self.check_case([],False,True)
    def test_running(self): self.check_case([{'run_id':'qa-123','status':'RUNNING'}],False)
    def test_unknown(self): self.check_case([{'run_id':'qa-123','status':'UNKNOWN'}],False)

if __name__ == '__main__': unittest.main()
