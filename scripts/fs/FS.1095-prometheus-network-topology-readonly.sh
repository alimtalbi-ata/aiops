#!/usr/bin/env bash
set -euo pipefail
echo "FS1095_MODE=READ_ONLY_NETWORK_TOPOLOGY"
for name in aiops2-rebuild-prometheus aiops2-rebuild-portal; do
 if ! docker inspect "$name" >/dev/null 2>&1;then echo "FS1095_ERROR=MISSING_CONTAINER_$name";exit 2;fi
 echo "FS1095_CONTAINER=$name STATUS=$(docker inspect "$name" --format '{{.State.Status}}')"
 echo "FS1095_NETWORKS_$name=$(docker inspect "$name" --format '{{range $name,$value := .NetworkSettings.Networks}}{{$name}} {{end}}')"
done
echo "FS1095_PRODUCTION_MUTATION=NONE"
echo "FS1095_RESULT=PASS"
