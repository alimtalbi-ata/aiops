#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
for p in 777 810 811 812 813 814 815 816; do grep -q "${p}" compose.yml || { echo "FAIL|missing_internal_port|$p"; exit 1; }; done
grep -q '8080:80' compose.yml
grep -q '5678:5678' compose.yml
grep -q '9090:9090' compose.yml
grep -q '3000:3000' compose.yml
! grep -RIn -E 'ports:.*7233|7233:7233' compose.yml || { echo 'FAIL|temporal_published'; exit 1; }
! grep -RIn 'network:.*aiops2-data' app || true
[ -s config/temporal/dynamicconfig/docker.yaml ] || { echo 'FAIL|missing_temporal_dynamicconfig'; exit 1; }
grep -q 'DYNAMIC_CONFIG_FILE_PATH: config/dynamicconfig/docker.yaml' compose.yml || { echo 'FAIL|missing_temporal_dynamicconfig_env'; exit 1; }
grep -q './config/temporal/dynamicconfig:/etc/temporal/config/dynamicconfig:ro' compose.yml || { echo 'FAIL|missing_temporal_dynamicconfig_mount'; exit 1; }
grep -q 'aiops2-temporal: {condition: service_healthy}' compose.yml || { echo 'FAIL|missing_temporal_health_gate'; exit 1; }
echo RUNTIME_CONTRACT=PASS
