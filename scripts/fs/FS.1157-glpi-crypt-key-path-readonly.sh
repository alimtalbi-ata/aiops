#!/usr/bin/env bash
# FS1157: read-only locate GLPI crypt key using installed container config and mounts.
set -euo pipefail
echo "FS1157_MODE=READ_ONLY_GLPI_KEY_DIRECTORY_DISCOVERY"
echo "FS1157_MUTATION=NONE"
echo "FS1157_PORTAL_MUTATION=NONE"
docker exec aiops2-rebuild-glpi sh -c '
  echo "FS1157_KEY_PATHS"
  find /var/www /etc /run /opt -name glpicrypt.key -type f -print 2>/dev/null | head -20 || true
  echo "FS1157_CONFIG_ENTRYPOINTS"
  for f in /var/www/glpi/inc/downstream.php /var/www/glpi/config/config_db.php /var/www/glpi/inc/based_config.php /var/www/glpi/src/Glpi/Kernel/Kernel.php; do
    if [ -f "$f" ]; then echo "FS1157_FILE=$f"; grep -nE "GLPI_CONFIG_DIR|GLPI_VAR_DIR|downstream|based_config" "$f" | head -18 || true; fi
  done
  echo "FS1157_CONSTANT_REFERENCES"
  grep -Rnl --include="*.php" "GLPI_CONFIG_DIR" /var/www/glpi/config /var/www/glpi/inc /var/www/glpi/src 2>/dev/null | head -15 || true
'
echo "FS1157_MOUNT_DESTINATIONS"
docker inspect -f '{{range .Mounts}}{{println .Destination}}{{end}}' aiops2-rebuild-glpi
echo "FS1157_FINAL_STATUS=READ_ONLY_COMPLETE"
