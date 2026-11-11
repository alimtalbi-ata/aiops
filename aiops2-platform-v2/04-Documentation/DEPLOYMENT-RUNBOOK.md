# Deployment runbook

PowerShell transfer:
```powershell
scp .\AIOps2-Platform-Kit-V2.0.zip aiops@10.79.94.202:/home/aiops/
```

Debian:
```bash
set -Eeuo pipefail
umask 077
cd /home/aiops
sha256sum AIOps2-Platform-Kit-V2.0.zip
unzip -t AIOps2-Platform-Kit-V2.0.zip
mkdir -p /home/aiops/aiops2-platform-kit-v2.0
unzip -o AIOps2-Platform-Kit-V2.0.zip -d /home/aiops/aiops2-platform-kit-v2.0
KIT=/home/aiops/aiops2-platform-kit-v2.0/AIOps2-Platform-Kit-V2.0
cd "$KIT"
sha256sum -c manifests/SHA256SUMS
chmod 700 scripts/*.sh 03-Tests/*.sh
./scripts/one-shot.sh --check
./scripts/one-shot.sh --install
```

The installer creates `/home/aiops/aiops2`, generates a private `.env`, validates Compose, builds and starts only project `aiops2-v2`, waits for readiness and runs smoke tests. It refuses to overwrite a destination containing an existing deployment.

Remote API access should use an SSH tunnel:
```powershell
ssh -N -L 18080:127.0.0.1:18080 aiops@10.79.94.202
```

If SSH disconnects or install fails, run `/home/aiops/aiops2/scripts/diagnose.sh` after reconnecting. Share only the report, never `.env`.
