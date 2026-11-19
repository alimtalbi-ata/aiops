#!/usr/bin/env bash
set -Eeuo pipefail
sha="${1:?expected source SHA}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]]
[[ "$(git rev-parse HEAD)" == "$sha" ]]
[[ -z "$(git status --porcelain)" ]]
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted ]]
out="$(mktemp -d)"
tag="aiops2-portal-qualification:$sha"
docker buildx build --load --build-context noc_scripts=./scripts --label "org.opencontainers.image.revision=$sha" --iidfile "$out/image-id" -f app/portal/Dockerfile -t "$tag" ./app
id="$(cat "$out/image-id")"
[[ "$id" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$(docker image inspect --format '{{.Id}}' "$tag")" == "$id" ]]
[[ "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$tag")" == "$sha" ]]
python3 - "$sha" "$id" <<'PY'
import json,sys
print(json.dumps({"source_sha":sys.argv[1],"local_image_id":sys.argv[2],"state":"BUILD_PASS","deploy_authorized":False,"registry_digest":None}))
PY
