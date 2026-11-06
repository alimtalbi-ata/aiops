# FS.1024 — Reproducible source / Core image pin

- `app/twin/fs_observations.py` was copied **unchanged** from the deployed Twin container after verifying SHA256 `2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb`.
- `deploy/compose.core-metrics-image.yml` is a versioned **third Compose override** that pins the deployed Core candidate image. It does not replace or capture the complete host-side override at `/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml`.
- When managing Core from the host, use `docker compose -p aiops2-metrics-cutover -f /home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml -f /home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml -f deploy/compose.core-metrics-image.yml config` to inspect the merged configuration; **do not run up** without separate approval.
- The exact production Twin candidate was built by overlaying the runtime module onto an earlier Twin image. The Dockerfile for a clean-source Twin build still needs a separate qualification before this can be described as a fully reproducible production image.
- Core/Twin were UP during FS.1021. This file does not claim ongoing monitoring or CI validation.
