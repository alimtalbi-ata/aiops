# Historical portal recovery — 2026-10-19

**Author:** Abdelhalim Talbi  
**Repository:** https://github.com/alimtalbi-ata/aiops  
**Status:** Recovery procedure committed; server-side package and SCP transfer are pending.

## Goal

Preserve only the historical portal material that may be needed to complete AIOps 2.0. Do not rebuild the old platform, copy entire container exports into the source tree, or modify running services. The ACME environment remains a demonstration narrative, not a production dependency.

## Confirmed source locations

- R33 source tree: `/home/aiops/exports/AIOPS-R33-LOGICAL-20261007-112249/03-SOURCES/V1/stack/live_console`
- Recovery root reported on the host: `/home/aiops/recovery/AIOPS-HISTORICAL-PORTAL-20261019-130658`
- Historical v1 console export: `containers/aiops_v1_live_console.tar` (reported size 180,038,656 bytes)
- V145 test console export: `containers/aiops_v1_live_console_v145_test.tar` (reported size 179,796,480 bytes)
- Additional UI validation export: `containers/aiops_v1_ui_validation_20261018-000409.tar` (reported size 180,038,144 bytes)
- V92 consolidated portal export was reported as only 1,024 bytes; its image metadata also returned a missing content blob. Treat V92 as unavailable until independently recovered and verified.
- R33 source files confirmed by inventory include `main.py`, `requirements.txt`, `Dockerfile`, `app/static/aiops-portal.html`, `app/static/app.js`, `campaign-studio.html/js`, `demo-studio-v2.html`, `index.html`, and `styles.css`. Export listings also confirmed `demo-director.html` and `demo-videos.html` in the historical console.

## Recovery method

Use `tools/recovery/collect-historical-portal.sh` to create a timestamped, minimal archive containing:

1. A whitelist of R33 portal source files.
2. The same selected source files extracted from the v1 and V145 container exports.
3. A textual V1-vs-V145 diff.
4. A manifest describing provenance, exclusions and qualification limits.
5. SHA-256 checksums for package contents and the resulting archive.

The script reads existing sources and exports only. It does not stop, restart, rebuild or reconfigure containers. It deliberately excludes environment files, credentials, databases, volumes, logs, caches, bytecode and backup files. This is source preservation, not runtime qualification.

## Run on SRV-DEB-05

Review the script before executing it. It can be fetched from the recovery branch:

```bash
set -eu
umask 077
mkdir -p /home/aiops/recovery/tools
curl -fsSL \
  https://raw.githubusercontent.com/alimtalbi-ata/aiops/recovery/historical-portal-20261019/tools/recovery/collect-historical-portal.sh \
  -o /home/aiops/recovery/tools/collect-historical-portal.sh
chmod 700 /home/aiops/recovery/tools/collect-historical-portal.sh
bash -n /home/aiops/recovery/tools/collect-historical-portal.sh
sed -n '1,240p' /home/aiops/recovery/tools/collect-historical-portal.sh
```

If the review is satisfactory, run:

```bash
bash /home/aiops/recovery/tools/collect-historical-portal.sh
```

The script prints the exact package and checksum paths. Verify them before transfer:

```bash
sha256sum -c /home/aiops/recovery/exports/AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-<timestamp>.tar.gz.sha256
tar -tzf /home/aiops/recovery/exports/AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-<timestamp>.tar.gz | head -80
```

Replace `<timestamp>` with the exact value printed by the script; do not type the placeholder literally.

## SCP to Windows

Run from PowerShell on the workstation, not from the Debian SSH prompt:

```powershell
$pkg = "AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-<timestamp>.tar.gz"
scp "aiops@10.79.94.202:/home/aiops/recovery/exports/$pkg" "$env:USERPROFILE\Downloads\"
scp "aiops@10.79.94.202:/home/aiops/recovery/exports/$pkg.sha256" "$env:USERPROFILE\Downloads\"
```

Then validate locally with a trusted SHA-256 comparison against the checksum displayed on the server. Keep the archive as a recovery artifact; do not commit the archive itself to GitHub.

## Intelligent GitHub ingestion

After transfer:

- Extract to a new isolated working directory, never over the active checkout.
- Compare R33, v1 export and V145 candidate by file hash and diff.
- Add only source files and fixes that are absent from the current AIOps 2.0 repository and demonstrably useful.
- Exclude secrets, runtime databases, generated caches, large binary exports and full container exports.
- Preserve provenance with source path, original export, SHA-256 and an explicit confidence/qualification label.
- Commit source/doc/test changes to a dedicated branch and open a PR. Never push unreviewed historical code directly to `main`.

## Acceptance criteria

- [ ] Archive created on the host without changing runtime state.
- [ ] SHA-256 validation passes.
- [ ] Archive transferred to Windows by SCP and local checksum matches.
- [ ] V1/V145 diff reviewed and useful changes identified.
- [ ] Selected source integrated in an isolated checkout with tests.
- [ ] Continuity record, component reuse matrix, tests and decision log updated in the same PR.
- [ ] No claim of build/runtime/E2E qualification until those tests actually run.
- [ ] PC11K5 fencing and ownership invariants remain untouched.
