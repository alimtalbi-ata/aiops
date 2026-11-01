# Existing Debian autonomy channel (SRV-DEB-05) — P0
This is **not** a new-host installer. It adds a bounded, read-only outbound telemetry channel to the **existing** AIOps2 host. It never accepts GitHub-supplied shell, jobs or deployment instructions.

## One-time host bootstrap (authorized operator)
1. Inspect `scripts/existing_host_observer.py` and the systemd units; set `AIOPS_ROOT` to the actual existing checkout (never assume a path).
2. Install the observer at `/opt/aiops2-observer/existing_host_observer.py` and unit files in `/etc/systemd/system/`. Do **not** run any installer or reset Docker.
3. Provide a **fine-grained token** with only Issues:write on `alimtalbi-ata/aiops`, in `/etc/aiops2-agent/github-token` owned by `aiops`, mode 0600; never commit or echo it. Ensure `aiops` can read only its token and inspect Docker without adding dangerous privileges. Docker socket access effectively grants root; do not add `aiops` to the docker group merely for telemetry. Prefer an operator-approved restricted Docker proxy or omit Docker checks.
4. Run `python3 scripts/existing_host_observer.py` locally without publishing; inspect the JSON and ensure no secrets. Only then set `AIOPS_PUBLISH=1` and run the one-shot service.
5. Enable `aiops2-observer.timer` after observing one successful issue #186 comment. Verify with `systemctl list-timers` and the GitHub comment timestamp. If no comment, status is **NOT VERIFIED**.
6. Rollback: `systemctl disable --now aiops2-observer.timer`; remove installed unit and observer files, revoke token. Never remove existing AIOps2 containers, volumes or networks.

## Boundaries
- No bidirectional execution yet: this is a **Debian → GitHub evidence** foundation. A separate allowlisted, signed, replay-protected typed-job controller needs a security review before enabling GitHub → Debian actions.
- Report fields contain only booleans/exit codes; commands' stdout/stderr are deliberately discarded. Hostname is redacted. A Git SHA must be explicitly qualified before deployment claims.
- Existing-host installation is independent of the **separate** clean-host deployment kit and its CI.
- Do not claim this unit was installed on SRV-DEB-05 without an actual host receipt.
