"""Offline tests of the historical unregistered activity body."""
import asyncio
import json
import unittest
from worker.int10c_activity_body import acme_simulated_no_effect, read_bounded_authority_response
from worker.acme_simulated_hitl import SandboxDenied, verify_no_effect_receipt
from test_worker_acme_simulated_hitl import INTENT, NOW, fixtures

class Response:
    def __init__(self, chunks, status=200):
        self.chunks, self.status_code, self.reads = chunks, status, 0
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def iter_content(self, chunk_size):
        assert chunk_size == 8192
        for chunk in self.chunks:
            self.reads += 1
            yield chunk

class ActivityTests(unittest.TestCase):
    def test_stream_cap_stops_before_next_chunk(self):
        r = Response([b"x"*8192]*5+[b"never"])
        with self.assertRaises(SandboxDenied):
            read_bounded_authority_response(r)
        self.assertEqual(r.reads, 5)

    def test_stream_invalid(self):
        for chunks, status in [([b"{}"], 403), (["{}"], 200),
                               ([b'{"x":1,"x":2}'], 200), ([b"[]"],200)]:
            with self.subTest(status=status, chunks=chunks), self.assertRaises(SandboxDenied):
                read_bounded_authority_response(Response(chunks,status))

    def test_stream_valid(self):
        self.assertEqual(read_bounded_authority_response(Response([b'{"x":',b'1}'])), {"x":1})

    def run_body(self, intent=INTENT, enabled=True, foreign=False):
        docs, calls = fixtures(), []
        origins = {k: "http://aiops2-"+k+":"+str(p) for k,p in
                   [("core",810),("twin",811),("policy",813)]}
        if foreign: origins["core"] = "http://foreign:810"
        class Session:
            trust_env = True
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def get(self,url,**kwargs):
                assert self.trust_env is False
                assert kwargs == dict(headers={"Authorization":"Bearer synthetic","Accept":"application/json"},
                                      timeout=8,allow_redirects=False,stream=True)
                calls.append(url)
                component = next(k for k,v in origins.items() if url.startswith(v+"/"))
                return Response([json.dumps(docs[component]).encode()])
        self.calls = calls
        return asyncio.run(acme_simulated_no_effect(intent, enabled=enabled, origins=origins,
                            token="synthetic", session_factory=Session, now=NOW))

    def test_six_readbacks_no_effect(self):
        r = self.run_body()
        self.assertEqual(len(self.calls),6)
        self.assertEqual(r["receipt_status"],"SIMULATED_NO_EFFECT")
        self.assertIs(r["effect_allowed"],False)
        self.assertIs(r["execution_allowed"],False)
        self.assertNotIn("synthetic",repr(r))

    def test_disabled_foreign_tenant_origin(self):
        for kwargs in [dict(enabled=False),dict(enabled=1),dict(foreign=True),
                       dict(intent=dict(INTENT,tenant_id="FOREIGN"))]:
            with self.subTest(kwargs=kwargs), self.assertRaises(SandboxDenied):
                self.run_body(**kwargs)
            self.assertEqual(self.calls,[])
