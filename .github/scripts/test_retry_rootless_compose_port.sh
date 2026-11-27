#!/usr/bin/env bash
set -euo pipefail

root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
mkdir "$root/bin"
cat > "$root/bin/docker" <<'DOCKER'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$CALLS"
count() { grep -c 'up -d --no-deps temporal-ui$' "$CALLS" || true; }
if [[ "$*" == *" rm -sf temporal-ui" ]]; then
  exit 0
fi
if [[ "$*" == *" up -d --no-deps temporal-ui" ]]; then
  case "$FAKE_MODE" in
    transient)
      if [[ "$(count)" == 1 ]]; then
        echo "RootlessKit PortManager.AddPort(): listen tcp4 127.0.0.1:32786: bind: address already in use" >&2
        exit 1
      fi
      echo "started"
      exit 0
      ;;
    nonport)
      echo "invalid compose configuration" >&2
      exit 42
      ;;
    exhausted)
      echo "RootlessKit PortManager.AddPort(): listen tcp4 127.0.0.1:32786: bind: address already in use" >&2
      exit 1
      ;;
    success)
      echo "started"
      exit 0
      ;;
  esac
fi
echo "unexpected fake docker invocation: $*" >&2
exit 99
DOCKER
chmod +x "$root/bin/docker"
export PATH="$root/bin:$PATH"

count() { grep -c "$1" "$2" || true; }

calls="$root/transient.calls"
CALLS="$calls" FAKE_MODE=transient bash .github/scripts/retry-rootless-compose-port.sh "$root" temporal-ui docker compose --project-name fixture
[[ "$(count 'up -d --no-deps temporal-ui$' "$calls")" == 2 ]]
[[ "$(count 'rm -sf temporal-ui$' "$calls")" == 1 ]]

calls="$root/nonport.calls"
if CALLS="$calls" FAKE_MODE=nonport bash .github/scripts/retry-rootless-compose-port.sh "$root" temporal-ui docker compose --project-name fixture; then
  echo "non-port failure unexpectedly succeeded" >&2
  exit 1
else
  status=$?
fi
[[ "$status" == 42 ]]
[[ "$(count 'up -d --no-deps temporal-ui$' "$calls")" == 1 ]]
[[ "$(count 'rm -sf temporal-ui$' "$calls")" == 0 ]]

calls="$root/exhausted.calls"
if CALLS="$calls" FAKE_MODE=exhausted bash .github/scripts/retry-rootless-compose-port.sh "$root" temporal-ui docker compose --project-name fixture; then
  echo "three persistent collisions unexpectedly succeeded" >&2
  exit 1
else
  status=$?
fi
[[ "$status" == 1 ]]
[[ "$(count 'up -d --no-deps temporal-ui$' "$calls")" == 3 ]]
[[ "$(count 'rm -sf temporal-ui$' "$calls")" == 2 ]]

calls="$root/success.calls"
CALLS="$calls" FAKE_MODE=success bash .github/scripts/retry-rootless-compose-port.sh "$root" temporal-ui docker compose --project-name fixture
[[ "$(count 'up -d --no-deps temporal-ui$' "$calls")" == 1 ]]
[[ "$(count 'rm -sf temporal-ui$' "$calls")" == 0 ]]

echo "Rootless Temporal UI port retry contract PASS (transient, non-port, exhausted, success)"
