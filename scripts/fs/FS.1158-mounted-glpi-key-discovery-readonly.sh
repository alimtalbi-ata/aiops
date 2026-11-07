#!/usr/bin/env bash
# FS1158: discover mounted GLPI crypt key path without exposing file contents.
set -euo pipefail
echo "FS1158_MODE=READ_ONLY_MOUNTED_GLPI_KEY_DISCOVERY"
echo "FS1158_MUTATION=NONE"
echo "FS1158_PORTAL_MUTATION=NONE"
docker exec aiops2-rebuild-glpi sh -c '
  echo "FS1158_MOUNT_KEY_PATHS"
  find /var/glpi -type f \( -name glpicrypt.key -o -name glpi.key \) -print 2>/dev/null | head -30 || true
  echo "FS1158_MOUNT_TOP_LEVEL"
  find /var/glpi -mindepth 1 -maxdepth 2 -type d -print 2>/dev/null | head -40 || true
  echo "FS1158_CONFIG_DIR_REFERENCES"
  grep -n -C 3 "GLPI_CONFIG_DIR" /var/www/glpi/src/Glpi/Application/Environment.php /var/www/glpi/src/Glpi/Application/SystemConfigurator.php 2>/dev/null | head -65 || true
'
echo "FS1158_FINAL_STATUS=READ_ONLY_COMPLETE"
