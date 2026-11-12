#!/usr/bin/env bash
set -Eeuo pipefail

BASE="$HOME/aiops2-operations"
PORTAL="aiops2-rebuild-portal"
LOG="$BASE/logs/glpi-copilot.log"

exec 9>"$BASE/glpi-copilot.lock"
flock -n 9 || exit 0

{
  echo "=== FS374 CYCLE $(date -u +%FT%TZ) ==="

  # Prevent reuse of a previous successful snapshot.
  docker exec "$PORTAL" \
    rm -f /tmp/fs373-evidence.json \
          /tmp/fs374-services.json

  if "$BASE/fs373-evidence.sh"; then
    echo "FS_EVIDENCE=FRESH"
  else
    echo "FS_EVIDENCE=UNAVAILABLE"
    docker exec "$PORTAL" \
      rm -f /tmp/fs373-evidence.json
  fi

  if docker exec -i "$PORTAL" \
      python -u - \
      < "$BASE/fs374-services.py"; then
    echo "SERVICE_EVIDENCE=COLLECTED"
  else
    echo "SERVICE_EVIDENCE=UNAVAILABLE"
    docker exec "$PORTAL" \
      rm -f /tmp/fs374-services.json
  fi

  # Refresh GLPI/Core correlation before processing.
  docker exec "$PORTAL" \
    rm -f /tmp/fs375-correlation.json

  if docker exec "$PORTAL" \
      python -u /tmp/fs375-correlate.py; then
    echo "FS375_CORRELATION=COLLECTED"
  else
    echo "FS375_CORRELATION=UNAVAILABLE"
    docker exec "$PORTAL" \
      rm -f /tmp/fs375-correlation.json
  fi

  # FS376: read-only correlation audit.
  docker exec "$PORTAL" \
    rm -f /tmp/fs376-audit.json

  if docker exec "$PORTAL" \
      python -u /tmp/fs376-audit.py; then
    echo "FS376_AUDIT=COLLECTED"
  else
    echo "FS376_AUDIT=UNAVAILABLE"
    docker exec "$PORTAL" \
      rm -f /tmp/fs376-audit.json
  fi

    # FS407B: synchronize the validated host script each cycle.
    docker cp \
      "$BASE/glpi_copilot_bridge.py" \
      "$PORTAL:/tmp/glpi_copilot_bridge.py"

    HOST_SHA="$(sha256sum \
      "$BASE/glpi_copilot_bridge.py" | awk '{print $1}')"

    PORTAL_SHA="$(docker exec "$PORTAL" \
      sha256sum /tmp/glpi_copilot_bridge.py \
      | awk '{print $1}')"

    if [ "$HOST_SHA" != "$PORTAL_SHA" ]; then
      echo "FS407_BRIDGE_HASH_MISMATCH"
      exit 1
    fi

    echo "FS407_BRIDGE_SYNC=VERIFIED"

  docker exec \
    -e AIOPS_COPILOT_MIN_TICKET_ID=147 \
    -e AIOPS_COPILOT_TICKET_LIMIT=100 \
    "$PORTAL" \
    python -u /tmp/glpi_copilot_bridge.py

} >> "$LOG" 2>&1
