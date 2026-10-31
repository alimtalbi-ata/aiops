"""Offline full-stage tests for rejected Critic: never proceed on audit errors."""
import ast
import pathlib
import unittest
from unittest.mock import Mock

SRC=pathlib.Path(__file__).resolve().parents[1]/'app/worker/main.py'
tree=ast.parse(SRC.read_text())
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('recover_committed_critic_block','_execute_stage_blocking')]
code=compile(ast.Module(body=nodes,type_ignores=[]),str(SRC),'exec')

class StageBlockTests(unittest.TestCase):
    def run_stage(self, persist_fails=False):
        calls=[]
        def call(method,url,payload):
            calls.append(('call',url,payload))
            if url.endswith('/events') and payload['event_type']=='STAGE_STARTED':
                return {'version':11,'sequence':3}
            if url.endswith('/events') and payload['event_type']=='CRITIC_COMPLETED':
                return {'version':12,'sequence':4}
            if url.endswith('/command') and payload['command']=='BLOCK':
                return {'version':13,'status':'BLOCKED'}
            raise AssertionError(('unexpected call',url,payload))
        def get(base,path,**kwargs):
            calls.append(('get',path,None))
            if path.endswith('/api/runs/R1'):
                return {'run':{'incident_id':'INC1','status':'RUNNING'},'events':[{
                    'stage':'DGX_ANALYST','event_type':'ANALYST_COMPLETED',
                    'payload':{'analysis_record_id':'ANL1','analysis':{
                        'severity':'P1','confidence':.9}}}]}
            if path.endswith('/api/evidence?run_id=R1'):
                return {'items':[{'evidence_id':'EV1','source':'twin-simulator'}]}
            if path.endswith('/api/scenarios/S1'):
                return {'scenario':{'name':'synthetic'}}
            raise AssertionError(path)
        def post(base,path,payload,**kwargs):
            calls.append(('post',path,payload))
            if path=='/api/intelligence/critic':
                return {'critique':{'validated':False,'diagnostic_confidence':.4,
                                    'final_recommendation':'HUMAN_APPROVAL','issues':['x']},
                        'provider':'test','model':'test'}
            if path.endswith('/critique-record'):
                return {'critique_id':'CRT1'}
            if path.endswith('/checkpoint'):
                return {'ok':True}
            if path.endswith('/critic-denial-resume'):
                return {'run_id':'R1','status':'BLOCKED','denial_hash':'a'.repeat(64),'version':13}
            raise AssertionError(path)
        def denial(*args):
            calls.append(('denial',None,None))
            if persist_fails: raise TimeoutError('simulated')
            return 'POL1'
        ns={'activity':Mock(info=lambda:Mock(attempt=1)),
            'call':call,'get_json':get,'post_json':post,
            'persist_critic_denial':denial,
            'critic_denial_input':lambda *args: {'mode':'DEMO','critic_validated':False},
            'AtomicDenialBlockError':type('AtomicDenialBlockError',(Exception,),{}),
            'CORE':'http://core','EVID':'http://evidence',
            'INTEL':'http://intelligence','ADMIN':'dummy',
            'hashlib':__import__('hashlib'),'json':__import__('json'),
            'DGX_HTTP_TIMEOUT_SECONDS':120,
            'log':Mock()}
        exec(code,ns)
        result=ns['_execute_stage_blocking']({
            'run_id':'R1','version':10,'stage':'DGX_CRITIC',
            'mode':'DEMO','scenario_id':'S1'},1)
        return result,calls

    def test_rejected_critic_records_policy_denial_then_blocks(self):
        result,calls=self.run_stage()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(result['policy_denial_recorded'])
        self.assertLess(next(i for i,c in enumerate(calls) if c[0]=='denial'),
                        next(i for i,c in enumerate(calls) if c[0]=='call' and c[1].endswith('/command')))
        self.assertEqual(sum(c[0]=='denial' for c in calls),1)

    def test_failed_denial_audit_still_blocks_and_reports_gap(self):
        result,calls=self.run_stage(persist_fails=True)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertFalse(result['policy_denial_recorded'])
        self.assertTrue(any(c[0]=='call' and c[1].endswith('/command')
                            and c[2]['command']=='BLOCK' for c in calls))
        self.assertFalse(any(c[0]=='post' and ('remediat' in c[1] or 'approval' in c[1]) for c in calls))

if __name__=='__main__':unittest.main()
