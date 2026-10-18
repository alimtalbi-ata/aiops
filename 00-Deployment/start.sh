#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
docker compose up -d --build
docker compose ps
