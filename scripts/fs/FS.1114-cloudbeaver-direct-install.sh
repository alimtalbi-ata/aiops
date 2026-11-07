#!/usr/bin/env bash
# FS1114: direct CloudBeaver CE installation on AIOps2, no SQL credentials in Git.
# Production-adjacent persistent service; requires explicit operator authorization.
set -euo pipefail

NAME=aiops2-rebuild-cloudbeaver
IMAGE="${CLOUDBEAVER_IMAGE:-dbeaver/cloudbeaver:latest}"
NETWORK=aiops2-rebuild-public
SECONDARY_NETWORK=aiops2-rebuild-integration
PORT="${CLOUDBEAVER_HOST_PORT:-8978}"
WORKSPACE_VOLUME=aiops2-cloudbeaver-workspace

echo "FS1114_MODE=DIRECT_CLOUDBEAVER_INSTALL"
echo "FS1114_IMAGE=$IMAGE"
echo "FS1114_BIND=0.0.0.0:$PORT"
echo "FS1114_PRODUCTION_PORTAL_MUTATION=NONE"

if [[ "${AIOPS_AUTHORIZE_PRODUCTION_CLOUDBEAVER:-}" != "YES" ]]; then
  echo "FS1114_STOP=EXPLICIT_PRODUCTION_AUTHORIZATION_REQUIRED"
  echo "Set AIOPS_AUTHORIZE_PRODUCTION_CLOUDBEAVER=YES only after approving the persistent service."
  exit 3
fi

[[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT >= 1024 && PORT <= 65535 )) || {
  echo "FS1114_ERROR=INVALID_PORT"; exit 2;
}
for n in "$NETWORK" "$SECONDARY_NETWORK"; do docker network inspect "$n" >/dev/null; done
docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}' | grep -Fx 'aiops2-portal:fs1073-csp-candidate' >/dev/null || {
  echo "FS1114_ERROR=UNEXPECTED_PORTAL_IMAGE"; exit 2;
}
if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "FS1114_STOP=CONTAINER_ALREADY_EXISTS"; exit 2
fi
if ss -ltnH "sport = :$PORT" 2>/dev/null | grep -q .; then
  echo "FS1114_STOP=PORT_IN_USE"; exit 2
fi

# Standard official Community image; override CLOUDBEAVER_IMAGE to pin a release.
docker pull "$IMAGE"
docker volume create "$WORKSPACE_VOLUME" >/dev/null
docker run -d \
  --name "$NAME" \
  --restart unless-stopped \
  --network "$NETWORK" \
  --publish "0.0.0.0:$PORT:8978/tcp" \
  --mount "type=volume,source=$WORKSPACE_VOLUME,target=/opt/cloudbeaver/workspace" \
  --security-opt no-new-privileges \
  "$IMAGE" >/dev/null

# Attach the integration network only after rootless Docker published the port.
docker network connect "$SECONDARY_NETWORK" "$NAME"

READY=NO
for attempt in $(seq 1 90); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$PORT/" 2>/dev/null || true)"
  if [[ "$code" == 200 || "$code" == 302 || "$code" == 303 ]]; then READY=YES; break; fi
  sleep 2
done

echo "FS1114_READY=$READY"
echo "FS1114_PORT=$(docker port "$NAME" 8978/tcp)"
echo "FS1114_WORKSPACE=$WORKSPACE_VOLUME"
echo "FS1114_NETWORKS=$(docker inspect "$NAME" --format '{{json .NetworkSettings.Networks}}')"
echo "FS1114_PORTAL_IMAGE=$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')"
if [[ "$READY" != YES ]]; then
  echo "FS1114_ERROR=SERVICE_NOT_READY"
  docker logs --tail 30 "$NAME" 2>&1 || true
  exit 1
fi
echo "FS1114_RESULT=SERVICE_RUNNING"
echo "FS1114_NEXT=COMPLETE_ADMIN_SETUP_AND_CONFIGURE_DATABASE_CONNECTIONS_WITH_APPROPRIATE_SQL_ROLES"
echo "FS1114_WARNING=PUBLIC_HTTP_PORT_REQUIRES_FIREWALL_AND_HTTPS_PROXY_FOR_UNTRUSTED_NETWORKS"
echo "FS1114_URL=http://SRV-DEB-05:$PORT/"
echo "FS1114_PORTAL_INTEGRATION=NOT_YET_DEPLOYED"
