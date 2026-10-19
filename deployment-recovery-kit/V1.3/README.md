# AIOps2 Deployment & Recovery Kit V1.3

Author: Abdelhalim Talbi  
Date: 2026-10-19

**Mode: recovery/staging only.** This kit does not claim to recreate the missing V2 Compose file. The historical deployment path referenced by Docker labels was absent in the supplied inventory. No active containers are restarted and no workflows are started by the read-only collection scripts.

## Identified source candidates
- V69 stack: `/home/aiops/exports/AIOPS-R33-LOGICAL-20261007-112249/03-SOURCES/V69/stack`
- Temporal stage: `/home/aiops/.temporal-stage-20261017-171712`
- Platform diagnostics: `/home/aiops/aiops-platform`

## Workflow
1. Run `scripts/preflight.sh`.
2. Run `scripts/collect-runtime.sh`, or use `scripts/run-detached.sh` for SSH-disconnect-safe collection.
3. Review the resulting report before staging.
4. Copy sources only with `scripts/prepare-stage.sh --prepare`.
5. Validate a real, reviewed Compose file with `scripts/deploy.sh --compose /absolute/path/compose.yml`.
6. Applying requires the additional `--apply` flag and interactive confirmation.

No passwords or tokens are stored in this repository. Do not run destructive Compose operations during recovery.
