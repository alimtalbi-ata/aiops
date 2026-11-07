#!/usr/bin/env bash
# FS1153: identify installed GLPI token transformation without printing secrets.
set -euo pipefail
echo "FS1153_MODE=READ_ONLY_GLPI_APP_TOKEN_IMPLEMENTATION"
echo "FS1153_MUTATION=NONE"
docker exec -i aiops2-rebuild-glpi sh -lc '
  for d in /var/www/glpi /var/www/html/glpi /var/www/html; do
    if [ -f "$d/src/APIClient.php" ]; then ROOT="$d";break;fi
  done
  if [ -z "${ROOT:-}" ]; then echo "FS1153_ERROR=GLPI_SOURCE_NOT_FOUND";exit 2;fi
  echo "FS1153_GLPI_SOURCE_ROOT=$ROOT"
  for f in "$ROOT/src/APIClient.php" "$ROOT/src/Glpi/Api/API.php" "$ROOT/apirest.php"; do
    if [ -f "$f" ]; then
      echo "FS1153_SOURCE_FILE=$f"
      grep -nE "app_token|App-Token|hash_token|hashToken|password_hash|password_verify|sodium|encrypt|decrypt|hash_hmac" "$f" | cut -c 1-220 | head -80 || true
    fi
  done
  grep -RlnE "ERROR_WRONG_APP_TOKEN_PARAMETER" "$ROOT/src" "$ROOT/inc" 2>/dev/null | head -12
'
echo "FS1153_FINAL_STATUS=READ_ONLY_COMPLETE"
