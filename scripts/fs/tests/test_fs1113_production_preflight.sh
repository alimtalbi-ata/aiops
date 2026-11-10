#!/usr/bin/env bash
# Regression: a mismatched production tag must stop FS1113 before candidate build.
# Runs with a fake docker executable; never accesses a Docker daemon.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
GATE="$ROOT/scripts/fs/FS.1113-history-race-candidate-validation.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
cat >"$TMP/bin/docker" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FS1113_DOCKER_CALLS"
if [[ "$1" == inspect && "$2" == aiops2-rebuild-portal ]]; then
  case "$4" in
    '{{.Config.Image}}') printf '%s\n' 'unexpected:production-image';;
    '{{.Id}}') printf '%s\n' 'container-id';;
    '{{.Image}}') printf '%s\n' 'image-id';;
    *) exit 41;;
  esac
  exit 0
fi
exit 42
MOCK
chmod +x "$TMP/bin/docker"
export FS1113_DOCKER_CALLS="$TMP/docker-calls"
set +e
PATH="$TMP/bin:$PATH" bash "$GATE" >"$TMP/out" 2>&1
rc=$?
set -e
if [[ "$rc" != 2 ]]; then
  cat "$TMP/out"
  echo "FAIL: expected fail-closed exit 2, got $rc" >&2
  exit 1
fi
grep -q '^FS1113_ERROR=UNEXPECTED_PRODUCTION_IMAGE$' "$TMP/out"
grep -q '^FS1113_RESULT=FAIL$' "$TMP/out"
grep -q '^FS1113_PRODUCTION_MUTATION=NONE_BY_THIS_SCRIPT$' "$TMP/out"
if grep -q 'image inspect\|build\|run\|create\|start' "$TMP/docker-calls"; then
  echo "FAIL: preflight performed an image/build/runtime operation" >&2
  exit 1
fi
echo "PASS: unexpected production image blocks FS1113 before candidate build"
