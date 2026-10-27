"""Fail-closed OpenAI-compatible chat adapter for NVIDIA NIM and CI Ollama.

No arbitrary tools, shell execution or production action capability.
"""
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

class LLMUnavailable(RuntimeError):
    pass

def configuration(env=None):
    env = os.environ if env is None else env
    provider = env.get("AIOPS_LLM_PROVIDER", "disabled").lower()
    if provider not in ("disabled", "nim", "ngx", "ollama_ci"):
        raise LLMUnavailable("unsupported LLM provider")
    if provider == "disabled":
        return {"provider": provider, "qualified": False}
    if provider == "ollama_ci" and env.get("CI") != "true":
        raise LLMUnavailable("ollama_ci is restricted to CI=true")
    url = env.get("AIOPS_LLM_BASE_URL", "").rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LLMUnavailable("invalid model endpoint")
    if provider == "ollama_ci" and (parsed.hostname not in ("127.0.0.1", "localhost") or parsed.scheme != "http"):
        raise LLMUnavailable("CI Ollama must use loopback HTTP")
    model = env.get("AIOPS_LLM_MODEL", "")
    if not model or len(model) > 128 or any(x in model for x in "\n\r"):
        raise LLMUnavailable("explicit model required")
    api_key = env.get("AIOPS_LLM_API_KEY", "")
    if provider in ("nim", "ngx") and not api_key:
        raise LLMUnavailable("NIM API key required")
    return {"provider": provider, "base_url": url, "model": model,
            "qualified": False, "provenance": "CI_SIMULATED_LLM" if provider == "ollama_ci" else "NIM_UNQUALIFIED",
            "api_key": api_key if provider in ("nim", "ngx") else ""}

def infer(messages, env=None, transport=None):
    cfg = configuration(env)
    if cfg["provider"] == "disabled":
        raise LLMUnavailable("model adapter disabled")
    if not isinstance(messages, list) or not (1 <= len(messages) <= 16):
        raise LLMUnavailable("invalid message count")
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") not in ("system", "user", "assistant"):
            raise LLMUnavailable("invalid message role")
        if not isinstance(msg.get("content"), str) or not (1 <= len(msg["content"]) <= 8000):
            raise LLMUnavailable("invalid message content")
    payload = json.dumps({"model": cfg["model"], "messages": messages, "stream": False,
                          "temperature": 0, "max_tokens": 512}).encode()
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = "Bearer " + cfg["api_key"]
    req = Request(cfg["base_url"] + "/v1/chat/completions", data=payload,
                  headers=headers, method="POST")
    try:
        if transport is None:
            with urlopen(req, timeout=25) as response:
                raw = response.read(1024 * 1024 + 1)
        else:
            raw = transport(req)
        if len(raw) > 1024 * 1024:
            raise LLMUnavailable("oversized model response")
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip() or len(content) > 16000:
            raise LLMUnavailable("invalid model response")
        return {"text": content, "model": cfg["model"], "provider": cfg["provider"],
                "provenance": cfg["provenance"], "runtime_authenticated": False,
                "production_qualified": False, "may_execute_actions": False}
    except (KeyError, IndexError, TypeError, ValueError, OSError) as exc:
        raise LLMUnavailable("model request failed or invalid response") from exc
