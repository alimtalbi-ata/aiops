#!/bin/sh
set -eu
ADDRESS="${TEMPORAL_ADDRESS:-aiops2-temporal:7233}"
NAMESPACE="${DEFAULT_NAMESPACE:-default}"
MAX_ATTEMPTS="${TEMPORAL_WAIT_ATTEMPTS:-60}"
SLEEP_SECONDS="${TEMPORAL_WAIT_SECONDS:-2}"
attempt=1
while ! temporal operator cluster health --address "$ADDRESS" >/dev/null 2>&1; do
  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "FAIL|temporal_cluster_unhealthy|$ADDRESS"
    exit 1
  fi
  sleep "$SLEEP_SECONDS"
  attempt=$((attempt + 1))
done
if temporal operator namespace describe -n "$NAMESPACE" --address "$ADDRESS" >/dev/null 2>&1; then
  echo "TEMPORAL_NAMESPACE_EXISTS=$NAMESPACE"
elif temporal operator namespace create -n "$NAMESPACE" --address "$ADDRESS" >/dev/null; then
  echo "TEMPORAL_NAMESPACE_CREATED=$NAMESPACE"
elif temporal operator namespace describe -n "$NAMESPACE" --address "$ADDRESS" >/dev/null 2>&1; then
  echo "TEMPORAL_NAMESPACE_EXISTS_AFTER_RACE=$NAMESPACE"
else
  echo "FAIL|temporal_namespace_create|$NAMESPACE"
  exit 1
fi
echo "TEMPORAL_NAMESPACE_SETUP=PASS"
