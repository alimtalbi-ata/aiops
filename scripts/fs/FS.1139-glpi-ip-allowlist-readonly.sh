#!/usr/bin/env bash
# FS1139 — read-only GLPI IP allowlist diagnosis. No secret values or IP changes.
set -euo pipefail
echo "FS1139_MODE=GLPI_IP_ALLOWLIST_READ_ONLY"
echo "FS1139_MUTATION=NONE"
echo "FS1139_GLPI_API_CONFIGURATION_SCHEMA"
docker exec -i aiops2-rebuild-glpi-db sh -c 'mariadb -uglpi -p"$MARIADB_PASSWORD" glpi --batch --skip-column-names' <<'SQL'
SELECT table_name,column_name FROM information_schema.columns
WHERE table_schema='glpi'
AND (column_name LIKE '%ip%' OR column_name LIKE '%range%' OR column_name LIKE '%api%')
AND table_name IN ('glpi_apiclients','glpi_configs','glpi_users','glpi_auths')
ORDER BY table_name,column_name;
SQL
echo "FS1139_API_CLIENT_RULES_REDACTED"
docker exec -i aiops2-rebuild-glpi-db sh -c 'mariadb -uglpi -p"$MARIADB_PASSWORD" glpi --batch --skip-column-names' <<'SQL'
SELECT table_name FROM information_schema.tables
WHERE table_schema='glpi' AND table_name='glpi_apiclients';
SQL
echo "FS1139_GLPI_CONTAINER_NETWORKS"
docker inspect aiops2-rebuild-glpi --format '{{range $name,$net := .NetworkSettings.Networks}}network={{$name}} ip={{$net.IPAddress}} gateway={{$net.Gateway}}{{println}}{{end}}'
echo "FS1139_CORE_CONTAINER_NETWORKS"
docker inspect aiops2-rebuild-core --format '{{range $name,$net := .NetworkSettings.Networks}}network={{$name}} ip={{$net.IPAddress}} gateway={{$net.Gateway}}{{println}}{{end}}'
echo "FS1139_HTTP_LOCAL_REQUEST_SOURCE"
docker exec -i aiops2-rebuild-glpi php <<'PHP'
<?php
$ch=curl_init('http://127.0.0.1/apirest.php/initSession');
curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_TIMEOUT=>5]);
$body=curl_exec($ch);$code=curl_getinfo($ch,CURLINFO_HTTP_CODE);
curl_close($ch);
$parsed=json_decode($body,true);
echo json_encode(['status'=>$code,'error_code'=>is_array($parsed)?($parsed[0]??null):null,
  'request_origin'=>'GLPI_CONTAINER_LOOPBACK','mutation'=>'NONE']).PHP_EOL;
PHP
echo "FS1139_FINAL_STATUS=READ_ONLY_COMPLETE"
