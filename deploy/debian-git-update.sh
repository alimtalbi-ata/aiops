#!/usr/bin/env bash
# Read-only preflight by default; --apply explicitly fast-forwards checked-out main.
set -Eeuo pipefail
umask 077
MODE="${1:---check}"
if [[ "$MODE" != "--check" && "$MODE" != "--apply" ]]; then
  echo "Usage: $0 [--check|--apply]" >&2; exit 64
fi
if [[ "$(id -u)" -eq 0 ]]; then
  echo "Refusing root execution; use the repository's deploy user" >&2; exit 65
fi
command -v git >/dev/null || { echo "git missing" >&2; exit 69; }
REPO_DIR="${AIOPS_REPO_DIR:-/opt/aiops}"
cd "$REPO_DIR"
[[ -d .git ]] || { echo "Not a git working tree: $REPO_DIR" >&2; exit 66; }
[[ "$(git rev-parse --show-toplevel)" == "$(pwd -P)" ]] || { echo "Run at repository root" >&2; exit 66; }
[[ -z "$(git status --porcelain --untracked-files=normal)" ]] || { echo "Dirty working tree: BLOCKED" >&2; exit 73; }
[[ "$(git branch --show-current)" == "main" ]] || { echo "Expected main branch: BLOCKED" >&2; exit 73; }
REMOTE="$(git remote get-url origin)"
case "$REMOTE" in
  git@github.com:alimtalbi-ata/aiops.git|https://github.com/alimtalbi-ata/aiops.git)
    ;;
  *) echo "Unexpected origin: BLOCKED" >&2; exit 73;;
esac
BEFORE="$(git rev-parse HEAD)"
echo "REPO=$REPO_DIR MODE=$MODE BEFORE=$BEFORE"
git fetch --no-tags origin main
TARGET="$(git rev-parse refs/remotes/origin/main)"
git merge-base --is-ancestor "$BEFORE" "$TARGET" || {
  echo "Non-fast-forward upstream: BLOCKED" >&2; exit 73;
}
echo "TARGET=$TARGET"
if [[ "$MODE" == "--check" ]]; then
  git diff --stat "$BEFORE" "$TARGET"
  echo "CHECK_OK: no working tree changes made"
  exit 0
fi
# Snapshot commit ID for rollback. Never reset automatically: manual review required.
STATE_DIR="${AIOPS_STATE_DIR:-$HOME/.local/state/aiops}"
mkdir -p "$STATE_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
printf '%s\n' "$BEFORE" > "$STATE_DIR/pre-update-$STAMP.sha"
git merge --ff-only "$TARGET"
echo "UPDATED=$(git rev-parse HEAD)"
echo "ROLLBACK_REFERENCE=$STATE_DIR/pre-update-$STAMP.sha"
echo "Code updated only; no compose restart, migrations or LIVE operations performed"
