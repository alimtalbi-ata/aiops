#!/usr/bin/env bash
# FS1140: inspect GLPI API client allowlist rows and preexisting FS1130 tickets.
# Read-only; never prints credentials, token hashes, ticket content or user data.
set -euo pipefail
echo "FS1140_MODE=READ_ONLY_GLPI_API_CLIENT_RULES_AND_TICKET_CORRELATION"
echo "FS1140_PRODUCTION_MUTATION=NONE"
echo "FS1140_PORTAL_7777_MUTATION=NONE"
docker exec -i aiops2-rebuild-glpi-db sh -c 'exec mariadb -uglpi -p"$MARIADB_PASSWORD" glpi --batch --skip-column-names' <<'SQL'
SELECT 'FS1140_GLPI_API_CLIENT_COLUMNS';
SELECT column_name,data_type FROM information_schema.columns
 WHERE table_schema='glpi' AND table_name='glpi_apiclients'
 AND column_name IN ('id','name','is_active','is_recursive','ipv4_range_start','ipv4_range_end','ipv6','entities_id')
 ORDER BY ordinal_position;
SELECT 'FS1140_GLPI_API_CLIENT_COUNT';
SELECT count(*) FROM glpi_apiclients;
SELECT 'FS1140_GLPI_API_CLIENT_SAFE_RULES';
SET @cols=(SELECT GROUP_CONCAT(CONCAT('`',column_name,'`') ORDER BY ordinal_position SEPARATOR ',')
 FROM information_schema.columns
 WHERE table_schema='glpi' AND table_name='glpi_apiclients'
 AND column_name IN ('id','name','is_active','ipv4_range_start','ipv4_range_end','ipv6'));
SET @query=CONCAT('SELECT ',COALESCE(@cols,'NULL'),' FROM glpi_apiclients ORDER BY id LIMIT 30');
PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
SELECT 'FS1140_FS1130_EXISTING_TICKETS_COUNT';
SELECT COUNT(*) FROM glpi_tickets
 WHERE name LIKE '%FS1130%' OR content LIKE '%FS1130%';
SELECT 'FS1140_DEMO_TICKETS_COUNT';
SELECT COUNT(*) FROM glpi_tickets WHERE name LIKE '[DEMO]%';
SQL
echo "FS1140_DOCKER_SHARED_NETWORKS"
docker inspect aiops2-rebuild-core aiops2-rebuild-glpi --format '{{.Name}} {{range $name,$net := .NetworkSettings.Networks}}{{$name}} {{end}}'
echo "FS1140_FINAL_STATUS=PASS_READ_ONLY"
