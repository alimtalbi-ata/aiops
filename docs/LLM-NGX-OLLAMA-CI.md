# NGX Mistral 192B / Ollama CI contract

The only simulated hardware dependency in GitHub Actions is the NVIDIA NGX LLM box. `app/shared/llm_adapter.py` is a small, fail-closed OpenAI-compatible chat-completions adapter. It is **not yet wired into the Copilot or Temporal Worker**; those components must be integrated and tested separately, and existing Copilot output must not be described as Mistral inference.

Providers: `disabled` (default); `ngx` (explicit NGX endpoint, no qualification implied); `ollama_ci` (only `CI=true`, loopback `http://127.0.0.1`, explicitly marked `CI_SIMULATED_LLM`). Configure `AIOPS_LLM_PROVIDER`, `AIOPS_LLM_BASE_URL`, `AIOPS_LLM_MODEL`; do not commit NGX credentials. Both providers must implement `/v1/chat/completions`. The adapter does not send credentials, use tools or execute commands; future NGX authentication must be designed before production use.

Fast tests are included in existing `.github/workflows/quality.yml`. Optional manual `.github/workflows/ollama-llm-contract.yml` starts a real Ollama process on an ephemeral runner and uses `qwen3:4b` by default, or `qwen3:8b` on demand. Model download and inference can be slow or exceed shared-runner resources; this workflow is opt-in. It verifies API and response provenance, not Mistral 192B quality, factual grounding or operational authorization. `test_llm_adapter.py` uses a deterministic in-process HTTP transport substitute to exercise failure paths; only the optional Ollama workflow exercises real inference. No live server or NVIDIA box is accessed.

Next: wire analyst/critic to the adapter behind evidence-grounding and policy controls, add identical NGX/Ollama schema checks, record model version and inference receipts, then qualify end-to-end in isolated CI. No production deployment.
