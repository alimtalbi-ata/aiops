import importlib.util
import pathlib
import unittest
from unittest.mock import patch

PATH = pathlib.Path(__file__).resolve().parents[2] / "scripts/ops/run_linkage_gate.py"
spec = importlib.util.spec_from_file_location("run_linkage_gate", PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class GateTests(unittest.TestCase):
    def test_run_id_validation(self):
        self.assertTrue(gate.RUN_RE.fullmatch("RUN-8CA56A39E58944F1"))
        self.assertFalse(gate.RUN_RE.fullmatch("RUN-'; DROP TABLE aiops.runs;--"))
    def test_no_mutating_commands(self):
        with patch.object(gate.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = '{"run":null}\n'
            gate.pg_query("SELECT json_build_object('run',null)::text;")
            args = run.call_args.args[0]
            self.assertEqual(args[:3], ["docker","exec","-i"])
            self.assertIn("READ ONLY",run.call_args.kwargs["input"])
    def test_external_ticket_is_not_verified(self):
        self.assertIn("NOT_API_VERIFIED", PATH.read_text())
    def test_parser_supports_wrappers(self):
        source = PATH.read_text()
        self.assertIn("('run','data','result')",source)
        self.assertIn("'parse_status':'UNRECOGNIZED'",source)
        self.assertIn('"AUTH_REQUIRED"',source)
    def test_no_side_effectful_http(self):
        source=PATH.read_text()
        self.assertIn("method='GET'",source)
        self.assertNotIn("method='POST'",source)
        self.assertNotIn("docker restart",source)

if __name__ == "__main__":
    unittest.main()

class AuthenticatedReadTests(unittest.TestCase):
    def collect(self, token='fixture-private-token', wrong_run=False):
        import contextlib
        import io
        import json
        import urllib.error
        rid='RUN-8CA56A39E58944F1'
        requests=[]
        def open_url(request,**kwargs):
            requests.append(request)
            path=request.full_url
            protected=path.endswith('/ai-ledger') or path.endswith('/policy-status')
            if protected and not request.get_header('Authorization'):
                raise urllib.error.HTTPError(path,401,'UNAUTHORIZED',{},None)
            if path.endswith('/ai-ledger'):
                value={'run_id':'RUN-OTHER' if wrong_run else rid,
                       'analyses':[{'analysis_id':'AN-1','output':{'confidence':.7},'authorization':token}],
                       'critiques':[{'critique_id':'CR-1','validated':False,
                                    'issues':['Unsupported diagnostic claim'],
                                    'output':{'unsafe_actions':[],'final_recommendation':'HUMAN_APPROVAL'}}],
                       'policy_decisions':[],'secret':token}
            elif path.endswith('/policy-status'):
                value={'run_id':rid,'policy_gate_state':'BLOCKED','secret':token}
            elif path.endswith('/evidence'):value={'items':[]}
            else:value={'run':{'run_id':rid,'incident_id':'INC-TEST','status':'BLOCKED'}}
            response=io.StringIO(json.dumps(value));response.status=200
            return response
        def execute(argv,stdin=None):
            output=io.StringIO()
            with patch('sys.argv',['-c',rid]), contextlib.redirect_stdout(output):
                exec(compile(argv[-2],'embedded-core-read','exec'),{})
            return output.getvalue()
        env={'AIOPS_INTERNAL_TOKEN':token} if token else {}
        with patch.dict('os.environ',env,clear=True), \
             patch('urllib.request.urlopen',side_effect=open_url), \
             patch.object(gate,'execute',side_effect=execute):
            result=gate.core_get(rid)
        return result,requests

    def test_authenticated_get_exposes_stored_critic_reason_without_token(self):
        import json
        result,requests=self.collect()
        ledger=result['ai_ledger']
        self.assertEqual(ledger['http'],200)
        self.assertEqual(ledger['data']['critiques'][0]['issues'],['Unsupported diagnostic claim'])
        self.assertTrue(all(r.get_method()=='GET' for r in requests))
        self.assertTrue(all(r.get_header('Authorization')=='Bearer fixture-private-token' for r in requests))
        self.assertNotIn('fixture-private-token',json.dumps(result))
        self.assertNotIn('authorization',ledger['data']['analyses'][0])

    def test_missing_internal_token_remains_unauthorized(self):
        result,_=self.collect(token=None)
        self.assertEqual(result['ai_ledger']['http'],401)
        self.assertFalse(result['ai_ledger']['accessible'])

    def test_wrong_run_ledger_is_not_projected(self):
        result,_=self.collect(wrong_run=True)
        self.assertEqual(result['ai_ledger']['error'],'ValueError')
        self.assertNotIn('data',result['ai_ledger'])
