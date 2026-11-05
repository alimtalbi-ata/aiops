#!/usr/bin/env bash
# V28 FS Worker runtime attestation. Read-only; never invokes /execute or changes Compose.
set -euo pipefail
container="${1:-aiops2-rebuild-worker}"
if [[ "$container" != "aiops2-rebuild-worker" ]]; then
  echo "REFUSED: only the V28 Worker container may be inspected" >&2; exit 64
fi
command -v docker >/dev/null || { echo "BLOCKED: docker unavailable" >&2; exit 69; }
command -v sha256sum >/dev/null || { echo "BLOCKED: sha256sum unavailable" >&2; exit 69; }
printf 'container=%s\n' "$container"
docker inspect --format 'image_id={{.Image}} image_ref={{.Config.Image}} state={{.State.Status}} pid={{.State.Pid}}' "$container"
docker inspect --format '{{range .Mounts}}mount={{.Type}}:{{.Source}}:{{.Destination}}:{{.RW}}{{println}}{{end}}' "$container"
# Hash the actual Python module imported by the running image, not a host-side candidate.
# Introspection uses a separate read-only process and is NOT proof of the running PID's import.
docker exec "$container" python -c 'import importlib,hashlib,pathlib; m=importlib.import_module("app.worker.main"); p=pathlib.Path(m.__file__).resolve(); print("module_path="+str(p)); print("module_sha256="+hashlib.sha256(p.read_bytes()).hexdigest())' || {
  echo "BLOCKED: module path/hash unavailable; no isolation attestation" >&2; exit 70;
}
echo 'RESULT=INSPECTION_ONLY_NOT_ISOLATION_PROOF'
echo 'NO_GO_EXECUTE: require active-process identity, SAN exclusion, negative tests, Evidence/Policy bindings'
