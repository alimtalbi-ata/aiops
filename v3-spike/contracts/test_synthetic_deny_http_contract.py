"""HTTP contract for C rootless kit: synthetic only, no production identity.
Expected endpoints: GET /health, POST /v1/synthetic/deny.
This is an integration acceptance contract, not proof of running kit.
"""
import json
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import os

BASE = os.environ.get("AIOPS_V3_SYNTHETIC_URL", "http://127.0.0.1:8088")

def call(method, path, data=None):
    request = Request(BASE + path, data=None if data is None else json.dumps(data).encode(),
                      headers={"Content-Type": "application/json"}, method=method)
    with urlopen(request, timeout=3) as response:
        return response.status, json.load(response)

@unittest.skipUnless(os.environ.get("AIOPS_V3_SYNTHETIC_HTTP_TEST") == "1",
                     "Requires isolated synthetic HTTP service explicitly enabled")
class SyntheticDenyHTTPContract(unittest.TestCase):
    def test_health(self):
        status, body = call("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "synthetic-only")

    def test_deny_digest_and_replay(self):
        import uuid
        nonce = "contract-" + uuid.uuid4().hex
        _, first = call("POST", "/v1/synthetic/deny", {"nonce": nonce})
        self.assertEqual(first["decision"], "DENY")
        self.assertTrue(first["accepted"])
        self.assertEqual(len(first["evidence"]["digest"]), 64)
        _, replay = call("POST", "/v1/synthetic/deny", {"nonce": nonce})
        self.assertFalse(replay["accepted"])
        self.assertIsNone(replay["evidence"])

    def test_untrusted_context_cannot_override_backend(self):
        import uuid
        for field, value in (("tenant_id", "foreign"), ("resource_id", "opaque:other"),
                             ("approval_id", "ALLOW"), ("evidence_digest", "0" * 64)):
            with self.subTest(field=field):
                _, body = call("POST", "/v1/synthetic/deny",
                               {"nonce": uuid.uuid4().hex, field: value})
                self.assertEqual(body["decision"], "DENY")
                self.assertFalse(body["accepted"])
                self.assertIsNone(body["evidence"])

    def test_duplicate_json_keys_rejected_without_nonce_consumption(self):
        import uuid
        nonce = "dup-" + uuid.uuid4().hex
        payload = ('{"nonce":"' + nonce + '","nonce":"' + nonce + '"}').encode()
        request = Request(BASE + "/v1/synthetic/deny", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        _, first = call("POST", "/v1/synthetic/deny", {"nonce": nonce})
        self.assertTrue(first["accepted"])
        _, replay = call("POST", "/v1/synthetic/deny", {"nonce": nonce})
        self.assertFalse(replay["accepted"])

    def test_bad_nonce_refused(self):
        for nonce in ("", "bad/nonce", "bad\\nnonce", "x" * 129):
            with self.subTest(nonce=nonce):
                _, body = call("POST", "/v1/synthetic/deny", {"nonce": nonce})
                self.assertFalse(body["accepted"])

if __name__ == "__main__":
    unittest.main()
