# Historical portal recovery result — 2026-10-19

**Author:** Abdelhalim Talbi  
**Repository:** https://github.com/alimtalbi-ata/aiops  
**Work branch:** `recovery/record-historical-portal-package-2026-10-19`  
**Status:** Selective source package created; package checksum verification and source-level review remain pending.

## Result recorded from SRV-DEB-05

The corrected collection script completed with:

- `RESULT=SOURCE_RECOVERY_PACKAGE_CREATED_NO_RUNTIME_CHANGES`
- `COLLECTOR_EXIT=0`
- Package: `/home/aiops/recovery/exports/AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-20261019-144103.tar.gz`
- Checksum sidecar: same path plus `.sha256`
- Reported package size: 756,799 bytes
- Reported diff size: 27,623 lines
- Reported staged file count: 33

These are host-reported collection results. They do **not** prove the package checksum is valid, that every source file is complete, or that the portal builds or runs.

## Inputs and provenance

- R33 source root: `/home/aiops/exports/AIOPS-R33-LOGICAL-20261007-112249/03-SOURCES/V1/stack/live_console`
- R33 application entry point: `app/main.py` (75,846 bytes, as reported by a read-only inventory)
- R33 UI assets confirmed present: `app/static/index.html`, `app/static/app.js`, `app/static/styles.css`, plus campaign/demo HTML and JavaScript files.
- V1 export: `aiops_v1_live_console.tar` (180,038,656 bytes)
- V145 test export: `aiops_v1_live_console_v145_test.tar` (179,796,480 bytes)
- Both exports were reported readable by `tar -tf`; selected whitelisted paths were found in both exports before collection.

## Important correction

The original collector incorrectly expected `$R33_SOURCE/main.py`. The actual entry point is `$R33_SOURCE/app/main.py`. A candidate patch was checked with `bash -n`, the prior script was preserved as a timestamped backup, and the corrected script completed the collection. Do not rerun the collector merely because the output archive was later mistaken for an executable command.

## What the package is and is not

The archive is a **selective source-recovery artifact** containing R33 source candidates, selected files from the V1 and V145 container exports, a text diff, a recovery manifest, and SHA-256 manifests according to the collector's output. The package itself has not yet been independently inspected in this session because the archive-inspection runtime was unavailable.

No claim is made that:
- the outer archive's SHA-256 check has passed;
- the files have been transferred to Windows and verified there;
- the diff has been semantically reviewed;
- the historical portal builds or passes API, UI, integration or end-to-end tests;
- any historical code is ready for production reuse.

## Next actions, in order

1. **Completed on SRV-DEB-05:** `sha256sum -c` returned `Réussi`; `tar -tzf "$PKG" >/dev/null` succeeded and printed `TAR_READABLE=YES`.
2. Transfer the archive and checksum sidecar by SCP to the Windows workstation; independently compare the downloaded file's SHA-256 with the server value.
3. Extract only into a new isolated workspace. Never overlay the active checkout or production files.
4. Review the manifest, per-file checksums, R33/V1/V145 source tree and the 27,623-line diff. Start with entry points, routes/API contracts, UI flows, dependencies, error handling and security boundaries.
5. Compare candidate functionality with the canonical AIOps 2.0 Portal/Core/Twin/Evidence/Policy/Worker/Temporal contracts. Reuse through explicit adapters where useful; do not add a parallel state owner.
6. Record every candidate as reuse unchanged, adapt behind adapter, replace, retire or unknown, with source hashes and evidence.
7. Add only reviewed source, tests and documentation to a follow-up branch/PR. Do not commit the archive, container exports, secrets, databases or runtime data to GitHub.

## Architecture and safety constraints

- The portal calls Core APIs; it must not write databases directly.
- Temporal/Worker remain the durable orchestration boundary; n8n remains an integration boundary, not the Run state owner.
- Missing, stale or contradictory evidence remains UNKNOWN and blocks unsafe progression.
- ACME is a demonstration narrative and synthetic scenario environment, not a production dependency.
- Preserve the PC11K5 chain: claim → fencing/ownership → preconditions → effect → evidence → reconciliation.
- No active services were intentionally changed by the recovery operation; recheck live state before any later deployment.

## Evidence level

**Confirmed by host output:** source-path inventory, historical export readability checks, corrected collector syntax check, package creation output and zero collector exit code. On 2026-10-19 the user ran `sha256sum -c` against the exact package sidecar and received `Réussi`; `tar -tzf "$PKG" >/dev/null` also completed and printed `TAR_READABLE=YES`. These confirm the server-side archive checksum and gzip/TAR readability for that file.  
**Pending:** SCP/workstation transfer verification, semantic source review, dependency/build tests, isolated integration/E2E and any live-runtime qualification.


## Transfer instructions — important shell boundary

The archive and sidecar have been verified on SRV-DEB-05: the user observed `sha256sum -c` returning `Réussi` and `tar -tzf` succeeding. A transfer attempt then ran PowerShell assignments in the remote Debian Bash shell and failed with `variable sans liaison`. No evidence indicates that the archive was damaged or that the transfer occurred.

**Do not paste PowerShell syntax at the `aiops@SRV-DEB-05:~$` prompt.** Keep that SSH session open. Open a separate local Windows PowerShell window from the Windows Start menu and run the following there:

```powershell
$Server = 'aiops@10.79.94.202'
$Remote = '/home/aiops/recovery/exports'
$Package = 'AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-20261019-144103.tar.gz'
$Dest = Join-Path $env:USERPROFILE 'Downloads'

scp "${Server}:${Remote}/${Package}" $Dest
if ($LASTEXITCODE -ne 0) { throw 'SCP archive failed; do not continue.' }
scp "${Server}:${Remote}/${Package}.sha256" $Dest
if ($LASTEXITCODE -ne 0) { throw 'SCP checksum sidecar failed; do not continue.' }

$Local = Join-Path $Dest $Package
$Expected = ((Get-Content -LiteralPath (Join-Path $Dest "${Package}.sha256") -Raw).Trim() -split '\\s+')[0]
$Actual = (Get-FileHash -LiteralPath $Local -Algorithm SHA256).Hash.ToLowerInvariant()
"EXPECTED=$Expected"
"ACTUAL=$Actual"
if ($Expected -ne $Actual) { throw 'SHA-256 mismatch: isolate/delete local copy and investigate.' }
'WINDOWS_TRANSFER_CHECK=PASS'
```

The server sidecar contains the server's absolute path in the checksum line; if the simple extraction above does not yield a 64-character digest, instead compare the hash printed by `Get-FileHash` against the first 64-hex-character value shown by `sha256sum -c`/`sha256sum` on the server. Do not type `exit` or close the SSH session as part of this transfer; it is not required.
