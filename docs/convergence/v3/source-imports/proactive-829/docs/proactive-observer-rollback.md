# AIOps2 proactive observer rollback

## Scope
This rollback disables only cron entries whose lines end with the exact tag
`# AIOPS2_PROACTIVE_OBSERVER_V1`. It does not stop, restart, delete, or modify
any pre-existing observer, application process, data file, or deployment.

## Procedure
1. Obtain explicit operations approval and confirm the host/user guard in
   `deploy/rollback-proactive-observer.sh` matches the intended Debian host.
2. Preserve the current crontab backup and review it before execution.
3. Execute the rollback script as the dedicated `aiops` user on the approved
   host. The script refuses any other user/host.
4. It removes only the tagged AIOps2 entries, verifies the resulting crontab,
   and restores the exact backup if verification fails.
5. Keep the backup path and stdout as the rollback receipt.

## Safety boundary
The script is not executed by CI and has not been run on Debian as part of this
qualification. CI tests use mocked `id`, `hostname`, `flock`, and `crontab`
commands to verify selective removal and preservation of unrelated entries.
A passing unit test is not proof of host-level cron state or runtime rollback.
