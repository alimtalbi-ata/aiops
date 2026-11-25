#!/usr/bin/env bash
set -euo pipefail
umask 077
export V3_ROOT="${V3_ROOT:-/srv/aiops-v3}"
[[ "$V3_ROOT" = /* && "$V3_ROOT" != / ]] || { echo "Absolute dedicated root required" >&2; exit 1; }
[[ "$(id -u)" != 0 ]] || { echo "Rootless user required" >&2; exit 1; }
docker info --format '{{json .SecurityOptions}}' | grep -q 'name=rootless' || { echo "Rootless daemon required" >&2; exit 1; }
mkdir -p "$V3_ROOT"
[[ "$(realpath "$V3_ROOT")" = "$V3_ROOT" && -O "$V3_ROOT" ]] || exit 1
mkdir -p "$V3_ROOT/data/postgres"
envfile="$V3_ROOT/poc.env"
if [[ ! -e "$envfile" ]]; then
  (set -o noclobber; printf 'V3_DB_PASSWORD=%s\nV3_LAB_TOKEN=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 32)" > "$envfile")
fi
[[ -f "$envfile" && ! -L "$envfile" && -O "$envfile" ]] || exit 1
chmod 600 "$envfile"
unset V3_DB_PASSWORD V3_LAB_TOKEN
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose=(docker compose --env-file "$envfile" -f "$here/compose.poc-source.yml")
"${compose[@]}" config --quiet
"${compose[@]}" up --build --wait --wait-timeout 300
"${compose[@]}" ps
