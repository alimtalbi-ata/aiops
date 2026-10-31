# Debian NVIDIA NIM runtime qualification

This probe gives an operator a repeatable, non-destructive way to verify that a Debian host can reach the configured OpenAI-compatible NVIDIA NIM endpoint and obtain a completion from the exact configured model.

It does **not** claim that AIOps2 Analyst/Critic or Temporal Worker are wired to NIM. It qualifies provider connectivity only. Application integration is a separate acceptance gate.

## Requirements

- Debian 12 (or another supported Python 3 host).
- Python 3.10+; standard library only.
- Network access from the Debian host to NGX at `http://10.79.94.31:8000/v1`.
- No API key or bearer token is used by this deployment.

## Run on Debian

From the AIOps2 repository root:

```bash
python3 scripts/qualify_nim_runtime.py \
  --timeout 120 \
  --report artifacts/nim-runtime-qualification.json
```

The script defaults to the NGX URL above and performs unauthenticated requests. It discovers a unique Nemotron 120B model ID from `/v1/models`; if the endpoint advertises multiple plausible models, it reports the available IDs and asks for an explicit `NIM_MODEL` rather than guessing.

## What it verifies

1. Base URL is valid HTTP(S); credentials, query strings and fragments embedded in the URL are rejected.
2. Unauthenticated `GET /v1/models` succeeds.
3. The exact configured model ID is present in the returned model list.
4. Unauthenticated `POST /v1/chat/completions` succeeds with a small synthetic probe prompt.
5. The completion returns the unique marker `AIOPS2_NIM_OK`.
6. Provider-reported token usage is recorded when present; absent usage stays null.
7. Latency, HTTP status, model identity and sanitized error class are written to a mode-0600 JSON report.

Exit codes:
- `0`: both model discovery and completion probe passed.
- `1`: endpoint/model/completion qualification failed.
- `2`: local configuration is invalid or incomplete.

The report intentionally omits the prompt body and full model response. A PASS proves connectivity and a basic completion only; it is not a Nemotron quality benchmark, load test, GPU qualification, or proof of AIOps2 Worker integration.

## CI

GitHub Actions runs offline unit tests for URL validation, exact model matching, completion marker enforcement and report minimization and model selection. CI does not require NIM, GPU access, or the Debian server.

## Next application-level gate

After connectivity passes, configure the Intelligence Gateway with the same exact NIM endpoint/model using secret injection, then prove separately:
- persisted Analyst invocation linked to a canonical Run;
- persisted independent Critic invocation;
- provider/model/latency/token provenance;
- evidence-grounded output validation;
- Temporal retry idempotency;
- Portal and GLPI visibility.

Never silently substitute Ollama or a synthetic provider when the configured NIM endpoint is unavailable.
