# FS.1022 — Core/Twin Prometheus metrics production handover

Date: 2026-11-06. Environment: SRV-DEB-05, Docker rootless, project `aiops2-metrics-cutover`.

## Verified production state (operator outputs)

- Twin: Prometheus target `aiops2-twin` UP; previous Twin container retained as `aiops2-rebuild-twin-fs1015-rollback`.
- Core: Prometheus target `aiops2-core` UP; `GET /metrics` returns HTTP 200 and `text/plain; charset=utf-8`.
- Core running image ID: `sha256:c31c2412af358fe93c680fa8f7193307c5b316aaba57a4b31b42296304818d67` (tag `aiops2-core:fs1017-metrics-candidate-20261106`).
- Previous Core image retained: `sha256:a41a250997460793b50b7eb5a5c41a637d1e39960ceb7e9664d2e1553bf784a7`.
- Core Compose image persistence: aligned after FS.1021; no additional container restart.
- Core Compose override changed on host: `/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml`.
- Backup retained: `/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml.fs1021-backup-20261106`.

## Executed gates

| Script | Observed result |
| --- | --- |
| FS.1017 | Candidate Core image built; ASGI /metrics 200 text/plain; production unchanged |
| FS.1018 | Compose and rollback preflight PASS |
| FS.1019 | Core-only Compose cutover PASS; Prometheus Core and Twin UP |
| FS.1020 | Read-only post-cutover audit PASS; persistent Compose image drift identified |
| FS.1021 | Persistent Compose image aligned; Core/Twin still UP; no restart |

## Operational caveats

The persistent Compose override is a **host-side file**. Its correction was verified on SRV-DEB-05; committing this document does not by itself store or distribute that host override. Back up and manage the override through the normal configuration-management process before rebuilding the host.

FS.1019 was executed with a temporary third Compose override pointing to the candidate image; FS.1021 then updated the persistent override. Keep the original Core image and the saved Compose file until a separately approved retention cleanup.

The Twin runtime exporter fix was introduced through a candidate runtime image; ensure its source and build provenance are separately captured before considering the repository change complete. Prometheus UP demonstrates successful scrape at validation time, not continuous availability.

## Recovery reference (manual, approval required)

For Core, inspect current Compose configuration and target health first. If a rollback is approved, restore the saved Compose override and recreate **only** the Core service with the original project and both Compose files. Recheck Core and Twin targets after recovery. Never recreate Twin as part of Core rollback.

## GitHub review

- Draft PR #448: https://github.com/alimtalbi-ata/aiops/pull/448
- Draft PR #447: https://github.com/alimtalbi-ata/aiops/pull/447

No merge or release is implied by this handover. Before review/merge, verify that runtime-only Twin changes, Core source, Docker build artifacts, and the host Compose override are reproducible from version-controlled assets.
