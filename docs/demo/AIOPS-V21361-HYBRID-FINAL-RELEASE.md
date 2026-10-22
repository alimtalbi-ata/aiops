# AIOps V2.13.6.1 — Hybrid Final release handoff

The presentation release is packaged independently from the production stack. A reviewed cumulative ZIP includes the V2.13.5 Executive STAR UI, V2.13.4 hybrid/replay tooling, architecture material, test sources, SHA-256 inventory and an out-of-place replay assembler.

## Baseline qualifications provided by operator
- V2.13.4: 9 Python tests PASS; offline historical replay assembly PASS; Chromium PASS.
- V2.13.5: 3 Python tests PASS; 7/7 Chromium E2E checks PASS.
- V2.13.6: 12 Python tests PASS; reused Executive UI E2E checks PASS.
- V2.13.6.1: 14 Python tests PASS in local packaging environment; Debian qualification still pending.

## Data boundary
- Executive STAR = SIMULATED_TARGET.
- Offline historical replay = OPERATOR_SUPPLIED_EXPORT, never independently authenticated.
- Evidence Center = UNATTESTED_OFFLINE.
- dgx_independently_attested = false.
- live_execution_qualified = false.
- executor_fencing_qualified = false.

Never commit operator export JSON, raw evidence, ticket payloads, screenshots with identifiers, or fully assembled replay unless independently reviewed and sanitized.

## Debian workflow
After transferring the cumulative ZIP and extracting in /home/aiops, from `AIOPS-V2.13.6.1-HYBRID-FINAL/01-Demo` run the 14 tests and the new `tools/assemble_release_v21361.py` with `--source`, a new `--output`, `--run`, `--ledger`, `--evidence`, and `--legacy-kit`. Then qualify `tests/chromium_hybrid.py` and `tests/chromium_executive_full.py` in the assembled output.

Do not overwrite existing local Compose files or operational services. Historical replay assembly is offline and never executes a remediation.
