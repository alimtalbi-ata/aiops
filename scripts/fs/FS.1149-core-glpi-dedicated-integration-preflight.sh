#!/usr/bin/env bash
# FS1149: qualification before a reversible Core→GLPI network/ACL rollout.
# Strictly read-only: no Docker connect, no GLPI SQL writes, no secrets printed.
set -euo pipefail
echo "FS1149_MODE=CORE_GLPI_DEDICATED_INTEGRATION_PREFLIGHT"
echo "FS1149_MUTATION=NONE"
echo "FS1149_PORTAL_7777_MUTATION=NONE"
docker inspect -f '{{.Name}} {{range $k,$v := .NetworkSettings.Networks}}network={{$k}} ip={{$v.IPAddress}} {{end}}' aiops2-rebuild-core aiops2-rebuild-glpi aiops2-rebuild-portal
echo "FS1149_GLPI_DB_API_CLIENT_COLUMNS"
docker exec -i aiops2-rebuild-glpi-db sh -lc 'exec mariadb -N -u glpi -p"$MYSQL_PASSWORD" glpi' <<'SQL'
select column_name,column_type,is_nullable,column_default
from information_schema.columns
where table_schema='glpi' and table_name='glpi_apiclients'
order by ordinal_position;
select 'api_client_count',count(*) from glpi_apiclients;
select 'api_client_rule',id,name,is_active,
 inet_ntoa(ipv4_range_start),inet_ntoa(ipv4_range_end)
from glpi_apiclients order by id;
SQL
echo "FS1149_GLPI_API_CLIENT_INDEXES"
docker exec -i aiops2-rebuild-glpi-db sh -lc 'exec mariadb -N -u glpi -p"$MYSQL_PASSWORD" glpi' <<'SQL'
select index_name,non_unique,group_concat(column_name order by seq_in_index)
from information_schema.statistics
where table_schema='glpi' and table_name='glpi_apiclients'
group by index_name,non_unique;
SQL
echo "FS1149_CORE_CONFIG_PRESENCE_ONLY"
docker exec -i aiops2-rebuild-core python - <<'PY'
import json,os
print(json.dumps({'type':'core_config_presence',
 'glpi_url_present':bool(os.getenv('AIOPS_GLPI_URL')),
 'glpi_app_token_present':bool(os.getenv('AIOPS_GLPI_APP_TOKEN')),
 'glpi_user_token_present':bool(os.getenv('AIOPS_GLPI_USER_TOKEN')),
 'glpi_tickets_required':os.getenv('AIOPS_GLPI_TICKETS_REQUIRED','false').lower()=='true',
 'secret_values_exposed':False},sort_keys=True))
PY
echo "FS1149_FINAL_STATUS=READ_ONLY_PREFLIGHT_COMPLETE"
