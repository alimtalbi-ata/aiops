# E21 actual model experiment — not production qualification

Stacked on E20. Run only on a disposable GitHub-hosted Ubuntu amd64 runner with rootless Docker, no product host access, no secrets, no real data. Actual local inference through two Ollama containers. Image manifest pinned to published linux/amd64 digest for 0.11.4:
https://hub.docker.com/layers/ollama/ollama/0.11.4/images/sha256-1514372d3cef7387b6202b253e761d820e00e44b28f268aad5029389d0479e99
Models: https://ollama.com/library/qwen2.5/tags (0.5b and 1.5b instruct). Published 12-hex fingerprints checked; full observed manifest digests captured before/after, not yet pre-pinned. Same model family, no independent-model attestation. CPU smoke deliberately small, not a recommended production model selection.

Three synthetic E18 history fixtures: forward, reverse, overlap. Strict 3/3 expected state plus two validated calls per case; missing/malformed/abstention results retained and fail quality gate, even if safe. No mock provider or retry on model failure. Wall latency and reported usage only; no cost/TTFT estimates. Artifacts saved progressively. Process deadline and job timeout, no claim of production cancellation. No real-service E2E, RAG, persistent telemetry or independent QA qualification. This workflow is branch-only, not a deployment or recurring schedule.
