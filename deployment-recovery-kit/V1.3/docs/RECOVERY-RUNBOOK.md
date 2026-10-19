# Recovery runbook

## Transfer from Windows PowerShell
```powershell
scp .\AIOps2-Deployment-Recovery-Kit-V1.3.zip aiops@10.79.94.202:/home/aiops/
```

## Verify and extract on Debian
```bash
cd /home/aiops
sha256sum AIOps2-Deployment-Recovery-Kit-V1.3.zip
unzip -t AIOps2-Deployment-Recovery-Kit-V1.3.zip
mkdir -p /home/aiops/aiops2-deployment-recovery-kit-v1.3
unzip -o AIOps2-Deployment-Recovery-Kit-V1.3.zip -d /home/aiops/aiops2-deployment-recovery-kit-v1.3
```

Run preflight and read-only collection first. Use the detached collector if SSH sessions disconnect. Stage copies only after checking disk capacity. Do not deploy until the exact Compose and overrides have been recovered and validated.
