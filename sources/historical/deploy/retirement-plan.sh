# Legacy retirement

1. Verify Big Bang qualification and backup.
2. Set `RETIRE_LEGACY=1` and run `deploy/install.sh` or run `deploy/retire-legacy.sh` separately.
3. The script stops only legacy container-name patterns and exports inspect metadata.
4. It does not remove volumes, images, networks or files.
5. After acceptance, old compose directories can be archived manually.
