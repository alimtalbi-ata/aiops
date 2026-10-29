#!/usr/bin/env bash

ROOTS=(
  /home/aiops/aiops2-p0-consolidation
  /home/aiops/aiops2-v2-delivery
  /home/aiops/aiops-github-archive-worktree
  /home/aiops/aiops-v28-demo
  /home/aiops/aiops2-auto-deploy/repo
  /home/aiops/aiops2-rebuild-kit/github-safe-worktree
)

for repo in "${ROOTS[@]}"; do
  echo
  echo "========== $repo =========="

  git -C "$repo" rev-parse --is-inside-work-tree \
    >/dev/null 2>&1 || continue

  echo "--- COMMITS ---"
  git -C "$repo" log --all \
    --regexp-ignore-case \
    --extended-regexp \
    --grep='glpi|itsm|hitl|aiops.bot|ticket|incident.console|approval' \
    --format='%h %s' \
    | head -35

  echo "--- FICHIERS HISTORIQUES ---"
  git -C "$repo" log --all --name-only --format= \
    | sort -u \
    | grep -Ei 'glpi|itsm|hitl|approval|ticket|bot|console' \
    | head -35

  echo "--- CODE ACTUEL ---"
  grep -RilE \
    'apirest.php|initSession|GLPI_API|GLPI_URL|glpi.*ticket|ticket.*glpi|aiops.bot' \
    "$repo/app" "$repo/integration" \
    --include='*.py' \
    --include='*.json' \
    --include='*.yml' \
    --include='*.yaml' \
    2>/dev/null \
    | head -25
done

echo
echo "========== ANCIENS WORKFLOWS N8N =========="
find /home/aiops -maxdepth 6 -type f \
  -iname '*.json' \
  -path '*/n8n/*' \
  2>/dev/null | head -60

echo
echo "RECHERCHE TERMINEE"
