# Historical AIOps portal recovery

Author: Abdelhalim Talbi

## Scope

This collector preserves only whitelisted portal source files from the R33 source tree and two Docker container exports (V1 and V145). It creates textual diffs, a SHA-256 inventory, and heuristic static-analysis findings. It does not stop/restart containers, change deployments, read databases/volumes, or qualify runtime behavior. Treat findings as review leads, not proof of vulnerabilities or correctness.

## Safe invocation on SRV-DEB-05

Do not paste PowerShell syntax into the Linux SSH shell. Do not use `source` or `.` to run the collector: execute it as a child process.

```bash
bash -n /home/aiops/recovery/tools/collect-historical-portal.sh
bash /home/aiops/recovery/tools/collect-historical-portal.sh
```

Avoid setting `set -e` in the interactive SSH shell. A failure should stop only the collector process, not terminate the SSH session. The collector itself uses strict mode and prints the package path and checksum on success. It does not use `exec`, `kill`, `docker stop`, or `docker restart`.

If syntax validation fails, do not run it. Preserve the current script and report the diagnostic output. The collector keeps its temporary staging directory on failure and prints `STAGING_PRESERVED=...` for inspection.

## Copy package to Windows

Run the following in a separate **PowerShell** window on Windows, not at the Linux prompt. Replace the package filename with the exact path printed by the collector.

```powershell
$Server = "aiops@10.79.94.202"
$Remote = "/home/aiops/recovery/exports"
$Package = "AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-YYYYMMDD-HHMMSS.tar.gz"
$Dest = Join-Path $env:USERPROFILE "Downloads"

scp "${Server}:${Remote}/${Package}" $Dest
scp "${Server}:${Remote}/${Package}.sha256" $Dest
Get-FileHash (Join-Path $Dest $Package) -Algorithm SHA256
Get-Content (Join-Path $Dest ($Package + ".sha256"))
```

Compare the hash from `Get-FileHash` to the first 64-character digest in the checksum file. The uploaded archive is not verified until those values match.

## Next qualification stages

1. Inspect the manifest and inventory; confirm no credentials or operational data were included.
2. Review V1/V145 and R33/V145 diffs, grouping changes by API contracts, UI behavior, safety gates, and dead/demo-only code.
3. Run Python syntax checks and dependency-resolution/build checks in an isolated workspace.
4. Add unit/contract tests before attempting any deployment integration.
5. Keep PC11K5 fencing/ownership invariants unchanged.
