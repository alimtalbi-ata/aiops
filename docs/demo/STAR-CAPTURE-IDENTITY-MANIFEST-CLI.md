# STAR capture identity manifest CLI

## Purpose
Use an operator-provided, nonsecret JSON identity manifest to generate the nine-cue capture readiness plan. This command invokes the existing `plan_capture_identity`, preserves distinct n8n `execution_by_cue` IDs, and **never** interprets readiness as an authenticated browser proof.

## Input (illustrative, not an actual execution)

```json
{"run_id":"RUN-DEMO-001","identifiers":{"alert_id":"ALT-001","execution_by_cue":{"correlate":"EXE-001","enrich":"EXE-002","analyze":"EXE-003","simulate":"EXE-004"},"ticket_id":"TKT-001","approval_id":"APR-001"}}
```

## Run (isolated offline)

```bash
python3 -m demo.star_capture_identity_cli /tmp/star-ids.json --output /tmp/star-ready.json
```

The output is JSON, created exclusively without overwriting a prior run. Unknown top-level input keys and invalid IDs fail closed. `capture_attempt_ready_count` means all required **strings have been supplied**; it does not prove the IDs exist in n8n, GLPI or Grafana. `runtime_proof_count` remains **zero**, and no live remediation is authorized. The example contains invented IDs for illustration only.

## Qualification and next step
`tests/test_star_capture_identity_cli.py` checks schema strictness, executable JSON output, exclusive file creation and duplicate execution-ID rejection. CI is configured in `star-capture-evidence.yml`; verify its exact commit result before qualifying. Next: a read-only authenticated Chromium E2E collector linking each cue to a verified run/execution/ticket/alert and timestamp, before the portal on `:17777` displays proof. Do not access Debian production without explicit authorization.
