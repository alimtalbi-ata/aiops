import json
import unittest
from app.shared.llm_adapter import configuration, infer, LLMUnavailable

CI_ENV = {"CI": "true", "AIOPS_LLM_PROVIDER": "ollama_ci",
          "AIOPS_LLM_BASE_URL": "http://127.0.0.1:11434",
          "AIOPS_LLM_MODEL": "qwen3:4b"}
MESSAGES = [{"role": "user", "content": "Reply with OK"}]

class LLMAdapterTests(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertEqual(configuration({})["provider"], "disabled")
        with self.assertRaises(LLMUnavailable):
            infer(MESSAGES, {})
    def test_ci_only(self):
        with self.assertRaises(LLMUnavailable):
            configuration({**CI_ENV, "CI": "false"})
    def test_loopback_only(self):
        with self.assertRaises(LLMUnavailable):
            configuration({**CI_ENV, "AIOPS_LLM_BASE_URL": "http://example.org:11434"})
    def test_no_credentials_in_url(self):
        with self.assertRaises(LLMUnavailable):
            configuration({**CI_ENV, "AIOPS_LLM_BASE_URL": "http://u:p@127.0.0.1:11434"})
    def test_response_provenance(self):
        def transport(req):
            payload = json.loads(req.data)
            self.assertEqual(payload["stream"], False)
            self.assertEqual(payload["temperature"], 0)
            self.assertEqual(req.full_url, "http://127.0.0.1:11434/v1/chat/completions")
            return json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode()
        result = infer(MESSAGES, CI_ENV, transport)
        self.assertEqual(result["provenance"], "CI_SIMULATED_LLM")
        self.assertFalse(result["production_qualified"])
        self.assertFalse(result["may_execute_actions"])
    def test_reject_tool_role(self):
        with self.assertRaises(LLMUnavailable):
            infer([{"role": "tool", "content": "rm -rf /"}], CI_ENV, lambda _: b"{}")
    def test_reject_malformed_response(self):
        with self.assertRaises(LLMUnavailable):
            infer(MESSAGES, CI_ENV, lambda _: b'{"choices":[]}')
    def test_ngx_not_attested(self):
        cfg = configuration({"AIOPS_LLM_PROVIDER": "ngx", "AIOPS_LLM_BASE_URL": "https://ngx.example.invalid", "AIOPS_LLM_MODEL": "mistral-192b"})
        self.assertEqual(cfg["provenance"], "NGX_UNQUALIFIED")
        self.assertFalse(cfg["qualified"])

if __name__ == "__main__":
    unittest.main()
