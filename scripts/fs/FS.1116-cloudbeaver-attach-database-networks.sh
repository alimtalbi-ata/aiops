#!/usr/bin/env bash
set -euo pipefail
CB=aiops2-rebuild-cloudbeaver
PORTAL=aiops2-rebuild-portal
NETWORKS=(aiops2-rebuild-data aiops2-rebuild-temporal-data)
declare -A DB_NET=(
 [aiops2-rebuild-postgres]=aiops2-rebuild-data
 [aiops2-rebuild-temporal-postgres]=aiops2-rebuild-temporal-data
 [aiops2-rebuild-glpi-db]=aiops2-rebuild-integration
)
declare -A DB_PORT=(
 [aiops2-rebuild-postgres]=5432
 [aiops2-rebuild-temporal-postgres]=5432
 [aiops2-rebuild-glpi-db]=3306
)
echo "FS1116_MODE=DIRECT_CLOUDBEAVER_PRODUCTION_DB_NETWORK_INTEGRATION"
echo "FS1116_DATABASE_MUTATION=NONE"
echo "FS1116_DATABASE_PORT_PUBLICATION=NONE"
[[ "${AIOPS_AUTHORIZE_CLOUDBEAVER_DB_NETWORKS:-}" == YES ]] || { echo "FS1116_ERROR=AUTHORIZATION_REQUIRED";exit 3; }
docker inspect "$CB" --format '{{.State.Running}}' | grep -Fx true >/dev/null
before="$(docker inspect "$PORTAL" --format '{{.Config.Image}}')"
echo "FS1116_PORTAL_IMAGE_BEFORE=$before"
for db in "${!DB_NET[@]}"; do
  docker inspect "$db" --format '{{.State.Running}}' | grep -Fx true >/dev/null || { echo "FS1116_ERROR=DATABASE_NOT_RUNNING name=$db";exit 2; }
  docker network inspect "${DB_NET[$db]}" >/dev/null
done
for net in "${NETWORKS[@]}"; do
  if docker inspect "$CB" --format '{{json .NetworkSettings.Networks}}' | python3 -c 'import json,sys;sys.exit(0 if sys.argv[1] in json.load(sys.stdin) else 1)' "$net"; then
    echo "FS1116_NETWORK=$net STATUS=ALREADY_ATTACHED"
  else
    docker network connect "$net" "$CB"
    echo "FS1116_NETWORK=$net STATUS=ATTACHED"
  fi
done
docker exec "$CB" sh -c 'test -d /opt/cloudbeaver/workspace' >/dev/null
for db in aiops2-rebuild-postgres aiops2-rebuild-temporal-postgres aiops2-rebuild-glpi-db; do
  net="${DB_NET[$db]}"
  port="${DB_PORT[$db]}"
  ip="$(docker inspect "$db" --format "{{with index .NetworkSettings.Networks \"$net\"}}{{.IPAddress}}{{end}}")"
  [[ -n "$ip" ]] || { echo "FS1116_ERROR=DB_IP_MISSING name=$db network=$net";exit 2; }
  if docker exec "$CB" sh -c 'timeout 4 sh -c "echo > /dev/tcp/$1/$2" 2>/dev/null' sh "$ip" "$port"; then
    echo "FS1116_DB=$db HOST=$db PORT=$port TCP=PASS"
  else
    # The CloudBeaver image may not have bash or /dev/tcp. Check connectivity
    # with Python in a short-lived Docker container on the target network.
    if docker run --rm --network "$net" --entrypoint python postgres:16-alpine -c 'import socket;socket.create_connection((__import__("sys").argv[1],int(__import__("sys").argv[2])),4).close()' "$db" "$port" >/dev/null 2>&1; then
      echo "FS1116_DB=$db HOST=$db PORT=$port TCP=NETWORK_PROBE_PASS_CLOUDBEAVER_UNVERIFIED"
    else
      echo "FS1116_DB=$db HOST=$db PORT=$port TCP=UNVERIFIED"
    fi
  fi
done
after="$(docker inspect "$PORTAL" --format '{{.Config.Image}}')"
[[ "$after" == "$before" ]] || { echo "FS1116_ERROR=PORTAL_IMAGE_CHANGED";exit 3; }
echo "FS1116_PORTAL_IMAGE_AFTER=$after"
echo "FS1116_CLOUDBEAVER_PORT=$(docker port "$CB" 8978/tcp)"
echo "FS1116_RESULT=NETWORKS_ATTACHED"
echo "FS1116_SQL_CONNECTIONS=CONFIGURATION_REQUIRED"
