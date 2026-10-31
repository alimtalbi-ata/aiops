# Debian NVIDIA NIM runtime qualification

This probe gives an operator a repeatable, non-destructive way to verify that a Debian host can reach the configured OpenAI-compatible NVIDIA NIM endpoint and obtain a completion from the exact configured model.

It does **not** claim that AIOps2 Analyst/Critic or Temporal Worker are wired to NIM. It qualifies provider connectivity only. Application integration is a separate acceptance gate.

## Requirements

- Debian 12 (or another supported Python 3 host).
- Python 3.10+; standard library only.
- Network access from the Debian host to the NIM endpoint.
- Exact model ID returned by the NIM `/v1/models` API.
- API key in an environment variable if the NIM deployment requires authentication.

## Run on Debian

From the AIOps2 repository root:

```bash
export NIM_BASE_URL='http://127.0.0.1:8000/v1'
export NIM_MODEL='YOUR_EXACT_NIM_MODEL_ID'
# Only if NIM requires bearer authentication:
read -rsp 'NIM API key: ' NIM_API_KEY; export NIM_API_KEY; echo

python3 scripts/qualify_nim_runtime.py \
  --timeout 60 \
  --report artifacts/nim-runtime-qualification.json

unset NIM_API_KEY
```

Do not put API keys in shell history, command-line arguments, reports, screenshots, or tickets. The script reads `NIM_API_KEY` from the process environment and never writes it to the report.

## What it verifies

1. Base URL is valid HTTP(S); credentials, query strings and fragments embedded in the URL are rejected.
2. Authenticated `GET /v1/models` succeeds.
3. The exact configured model ID is present in the returned model list.
4. Authenticated `POST /v1/chat/completions` succeeds with a small synthetic probe prompt.
5. The completion returns the unique marker `AIOPS2_NIM_OK`.
6. Provider-reported token usage is recorded when present; absent usage stays null.
7. Latency, HTTP status, model identity and sanitized error class are written to a mode-0600 JSON report.

Exit codes:
- `0`: both model discovery and completion probe passed.
- `1`: endpoint/model/completion qualification failed.
- `2`: local configuration is invalid or incomplete.

The report intentionally omits the API key, prompt body and full model response. A PASS proves connectivity and a basic completion only; it is not a Nemotron quality benchmark, load test, GPU qualification, or proof of AIOps2 Worker integration.

## CI

GitHub Actions runs offline unit tests for URL validation, exact model matching, completion marker enforcement and credential non-disclosure. CI does not require NIM, GPU access, or the Debian server.

## Next application-level gate

After connectivity passes, configure the Intelligence Gateway with the same exact NIM endpoint/model using secret injection, then prove separately:
- persisted Analyst invocation linked to a canonical Run;
- persisted independent Critic invocation;
- provider/model/latency/token provenance;
- evidence-grounded output validation;
- Temporal retry idempotency;
- Portal and GLPI visibility.

Never silently substitute Ollama or a synthetic provider when the configured NIM endpoint is unavailable.
