#!/usr/bin/env bash
# FS1155: inspect installed GLPIKey class namespace and bootstrap. Read-only.
set -euo pipefail
echo "FS1155_MODE=GLPIKEY_CLASS_RESOLUTION_READ_ONLY"
echo "FS1155_MUTATION=NONE"
docker exec -i aiops2-rebuild-glpi sh -lc '
  ROOT=/var/www/glpi
  echo "FS1155_GLPIKEY_DECLARATIONS"
  grep -RnlE "(class[[:space:]]+GLPIKey|class[[:space:]]+Key)" "$ROOT/src" "$ROOT/inc" 2>/dev/null | head -20
  echo "FS1155_GLPIKEY_REFERENCES"
  grep -nE "GLPIKey|namespace|^use " "$ROOT/src/APIClient.php" | head -45
  echo "FS1155_BOOTSTRAP"
  for f in "$ROOT/inc/includes.php" "$ROOT/src/Glpi/Encryption/GLPIKey.php" "$ROOT/src/GLPIKey.php"; do
    if [ -f "$f" ]; then echo "FS1155_FILE=$f"; grep -nE "namespace|class GLPIKey|class_alias|autoload" "$f" | head -18 || true; fi
  done

'
echo "FS1155_FINAL_STATUS=READ_ONLY_COMPLETE"
