# NGX Mistral 192B / Ollama CI contract

The only simulated hardware dependency in GitHub Actions is the NVIDIA NGX LLM box. `app/shared/llm_adapter.py` is a small, fail-closed OpenAI-compatible chat-completions adapter. It is **not yet wired into the Copilot or Temporal Worker**; those components must be integrated and tested separately, and existing Copilot output must not be described as Mistral inference.

Providers: `disabled` (default); `nim` (`ngx` alias, explicit NVIDIA NIM endpoint, no qualification implied); `ollama_ci` (only `CI=true`, loopback `http://127.0.0.1`, explicitly marked `CI_SIMULATED_LLM`). Configure `AIOPS_LLM_PROVIDER`, `AIOPS_LLM_BASE_URL`, `AIOPS_LLM_MODEL` and for NIM `AIOPS_LLM_API_KEY` via a secret; never commit credentials. Both providers must implement `/v1/chat/completions`. The adapter sends a configured bearer token only for NIM/NGX; Ollama CI never receives that token. It does not use tools or execute commands. NIM transport security, trust boundaries and production qualification still require review.

Fast tests are included in existing `.github/workflows/quality.yml`. Optional manual `.github/workflows/ollama-llm-contract.yml` starts a real Ollama process on an ephemeral runner and uses `qwen3:4b` by default, or `qwen3:8b` on demand. Model download and inference can be slow or exceed shared-runner resources; this workflow is opt-in. It verifies API and response provenance, not Mistral 192B quality, factual grounding or operational authorization. `test_llm_adapter.py` uses a deterministic in-process HTTP transport substitute to exercise failure paths; only the optional Ollama workflow exercises real inference. No live server or NVIDIA box is accessed.

Next: wire analyst/critic to the adapter behind evidence-grounding and policy controls, add identical NGX/Ollama schema checks, record model version and inference receipts, then qualify end-to-end in isolated CI. No production deployment.

## Switching target only

NIM: `AIOPS_LLM_PROVIDER=nim`, `AIOPS_LLM_BASE_URL=https://<nim-host>`, `AIOPS_LLM_MODEL=<served-model-id>`, `AIOPS_LLM_API_KEY=<secret>`.

GitHub Actions: `AIOPS_LLM_PROVIDER=ollama_ci`, `AIOPS_LLM_BASE_URL=http://127.0.0.1:11434`, `AIOPS_LLM_MODEL=qwen3:4b`, `CI=true`. The caller invokes `infer(messages)` unchanged. NIM and Ollama model IDs and authentication differ, but the chat completion schema remains the same. NIM model availability and actual compatibility are not yet tested.
