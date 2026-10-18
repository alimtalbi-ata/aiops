# Big Bang deployment

1. Back up the old environment and verify checksums/restore tests.
2. Copy this kit to the new deployment directory.
3. Run `RETIRE_LEGACY=1 ./deploy/install.sh` only after the backup is confirmed. Legacy retirement stops old AioOps containers but never deletes their volumes/images.
4. Preflight checks Docker/Compose and disk capacity.
5. Build application images and start the normalized stack.
6. Qualification checks all expected containers and exposed health endpoints.
7. Synthetic E2E launches the Golden Payment scenario through Portal → Core → Temporal → Worker.
8. Review the Run, gates, evidence and Twin state before declaring acceptance.
