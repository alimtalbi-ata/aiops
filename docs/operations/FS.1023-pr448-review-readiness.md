# FS.1023 — PR #448 review readiness / source provenance

Date: 2026-11-06. Branch: `fix/fs-1009-twin-decimal-metrics`; base: `fix/fs-1002-prometheus-metrics-content-type`.

## Review result: NOT READY TO MERGE

GitHub compare showed 19 commits ahead of the base and 15 changed files: documentation and `scripts/fs/FS.1009.sh` through `FS.1021.sh`. **No application source or Dockerfile changes occur in this PR's diff.** This is not a claim that the base branch lacks the Core/Twin metrics text/plain change; both `app/core/main.py` and `app/twin/main.py` on the head branch already use `PlainTextResponse`.

### Blocking provenance gap — Twin

The deployed Twin image contains `/app/twin/fs_observations.py` with a Decimal-safe filesystem exporter, but the GitHub branch does not carry that module under `app/twin/`. The candidate builder `FS.1009.sh` copies the source from the then-running container and patches it; therefore a clean source checkout alone cannot reproduce that runtime module or the deployed image. Record the complete reviewed source in version control and provide a clean image build and contract test before merging. Do not blindly reconstruct the module from incomplete snippets.

### Blocking configuration gap — Core

FS.1021 modified the host file `/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml`, changing the effective Core image from `aiops2-core:fs-real-registration-20261105` to `aiops2-core:fs1017-metrics-candidate-20261106`. The change was verified live, but the host file is not part of this PR diff. Add the canonical Compose override to managed source/configuration and document its deployment path before claiming the PR reproduces production.

### Documentation correction

`docs/qualification/FS-1009-TWIN-DECIMAL-METRICS-2026-11-06.md` still says endpoint qualification is pending. Later FS.1011, FS.1015 and FS.1020 operator outputs demonstrate successful candidate endpoint checks, production cutover and Prometheus UP. Update that qualification document to link to the later gates and remove its stale overall status, while retaining the historical limits of FS.1009 alone.

## Verified operator evidence

- FS.1019: Core Compose cutover PASS; Core/Twin Prometheus UP.
- FS.1020: Core/Twin live metrics PASS; Core Compose persistence drift found.
- FS.1021: persistent Core image ALIGNED; Core/Twin Prometheus UP; no restart; backup retained.

These are observations at execution time, not a CI or continuous availability guarantee.

## Release gate

Keep PR #448 in draft; do not merge or mark ready for review until (1) Twin runtime source and build provenance, (2) Core Compose override provenance, and (3) qualification documentation are addressed. No production changes are required for this review.
