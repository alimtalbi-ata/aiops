# Optional Temporal technical console (V3 laboratory)
After the normal rootless source-kit launcher, use the same dedicated project and environment:
```bash
export V3_ROOT="${V3_ROOT:-/srv/aiops-v3}"
# Run from repository root; the dedicated root must already be initialized.
project="aiops-v3-poc-$(printf %s "$V3_ROOT" | sha256sum | cut -c1-12)"
docker info --format '{{json .SecurityOptions}}' | grep -q name=rootless
docker compose --project-name "$project" --env-file "$V3_ROOT/poc.env" -f v3-spike/kit/compose.poc-source.yml --profile orchestration up -d temporal-ui worker
docker compose --project-name "$project" --env-file "$V3_ROOT/poc.env" -f v3-spike/kit/compose.poc-source.yml --profile orchestration port temporal-ui 8080
```
Only use the returned loopback port and reject protected ports 7770/7777/7790. UI 2.56.4 is requested explicitly; actual image pull, digest capture, workflow lookup and history readback are CI gates. No public binding or persistent UI volume. TEMPORAL_DISABLE_WRITE_ACTIONS=true disables UI workflow actions; it is not an authenticated RBAC or tenant authorization guarantee. Do not expose this console externally. GAMMA remains the business interface. Temporal COMPLETED is transport completion; Core BLOCKED is the correct business disposition until qualified stage adapters exist. No production authorization. Current receipt checks cover completed workflow history after restart, not in-flight replay or full backup/restore.
