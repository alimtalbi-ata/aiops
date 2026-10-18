#!/usr/bin/env bash
set -Eeuo pipefail
ARCHIVE_ROOT="${LEGACY_ARCHIVE_ROOT:-/home/aiops/archive}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ARCHIVE_ROOT/aiops-legacy-retirement-$STAMP"
mkdir -p "$OUT"
LEGACY_RE='^aiops_v1_|^aiops-temporal-(integration|fastpath)|^aiops_v1_live_console'
mapfile -t C < <(docker ps -a --format '{{.Names}}' | grep -E "$LEGACY_RE" || true)
printf '%s\n' "${C[@]:-NONE}" > "$OUT/containers.txt"
for c in "${C[@]}"; do docker inspect "$c" > "$OUT/${c}.inspect.json"; done
if [ "${CONFIRM_RETIRE:-NO}" != "YES" ]; then echo 'RETIREMENT_ACTION=SKIPPED|set CONFIRM_RETIRE=YES after qualification'; exit 0; fi
if ((${#C[@]})); then printf '%s\n' "${C[@]}" | xargs -r docker stop >/dev/null; fi
cat > "$OUT/manifest.json" <<EOF
{"created_utc":"$STAMP","containers_stopped":${#C[@]},"volumes_deleted":false,"images_deleted":false,"networks_deleted":false}
EOF
echo "LEGACY_RETIREMENT_ARCHIVE=$OUT"
echo "LEGACY_CONTAINERS_STOPPED=${#C[@]}"
echo 'LEGACY_DATA_DELETED=NO'
echo 'LEGACY_VOLUMES_DELETED=NO'
echo 'LEGACY_IMAGES_DELETED=NO'
