#!/usr/bin/env bash
set -euo pipefail
echo "FS1141_MODE=READ_ONLY_IDENTIFY_GLPI_ALLOWED_IP"
echo "FS1141_PRODUCTION_MUTATION=NONE"
echo "FS1141_ALLOWED_IP=172.21.0.2"
echo "FS1141_DOCKER_CONTAINER_OWNER"
docker ps -q | while IFS= read -r id; do
  docker inspect "$id" --format '{{.Name}}{{range $name,$net := .NetworkSettings.Networks}}{{if eq $net.IPAddress "172.21.0.2"}} MATCH network={{$name}} ip={{$net.IPAddress}}{{end}}{{end}}'
done | grep ' MATCH ' || echo "FS1141_NO_RUNNING_CONTAINER_WITH_ALLOWED_IP"
echo "FS1141_PUBLIC_NETWORK_CONTAINERS"
docker network inspect aiops2-rebuild-public --format '{{range $id,$c := .Containers}}{{println $c.Name $c.IPv4Address}}{{end}}'
echo "FS1141_GLPI_API_CLIENT_METADATA_NO_TOKENS"
docker exec -i aiops2-rebuild-glpi-db sh -c 'exec mariadb -uglpi -p"$MARIADB_PASSWORD" glpi --batch --skip-column-names' <<'SQL'
SELECT id,name,is_active,INET_NTOA(ipv4_range_start),INET_NTOA(ipv4_range_end),ipv6
FROM glpi_apiclients ORDER BY id;
SQL
echo "FS1141_GLPI_WEB_RUNTIME"
docker inspect aiops2-rebuild-glpi --format 'name={{.Name}} networks={{range $name,$net := .NetworkSettings.Networks}}{{$name}}:{{$net.IPAddress}} {{end}}'
echo "FS1141_FINAL_STATUS=PASS_READ_ONLY"
