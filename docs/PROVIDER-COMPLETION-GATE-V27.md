# Provider completion integrity — V27 candidate (2026-10-20)

**Scope:** Analyst and Critic OpenAI-compatible HTTP response boundary. **Author:** Abdelhalim Talbi.

## Defect and change

Previously, `call_model` accepted any parseable JSON from `choices[0].message.content` without checking whether generation finished. A truncated generation can contain a syntactically valid but semantically incomplete JSON object.

The new shared `extract_complete_completion` guard requires exactly one choice, `finish_reason=stop`, `message.role=assistant`, non-empty text, and no refusal, tool call or function call. The same guard is applied to the initial Analyst/Critic response and the one bounded Critic schema-repair response. Missing metadata fails closed with HTTP 502; it is not a signal to retry or to authorize effects.

## Qualification and limitations

- Offline helper unit tests: six tests PASS locally on 2026-10-20, no network.
- Integrated mocked HTTP regressions are committed for GitHub CI; **their outcome is pending until the exact branch SHA's workflow completes**.
- CI container builds, disposable SQL migration tests, Temporal E2E and release ZIP are separate gates. A passing synthetic provider is not a real-model inference result.
- Real DGX/Mistral/Qwen endpoint inference, holdout evidence grounding, Debian deployment, LIVE Policy/HITL and PC11K5 fencing remain **NOT QUALIFIED**.
- Some OpenAI-compatible endpoints omit `finish_reason`; this is an intentional fail-closed compatibility boundary, not permission to assume completion. Verify the provider contract before promotion.
- No secrets or raw provider responses are logged. No deployment or production database changes.

## Next gates

1. Require all CI jobs PASS on the exact commit and verify cumulative kit checksum.
2. Run an explicitly authorized, read-only real-model Analyst/Critic holdout with provider finish metadata, citations and rejection/contradiction metrics; do not persist secrets or enable LIVE actions.
3. Reconcile provider compatibility and model latency with the Temporal activity timeout before any staged rollout.
