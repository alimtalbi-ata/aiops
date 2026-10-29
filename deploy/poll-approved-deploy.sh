#!/usr/bin/env bash
# Poll a reviewed deployment branch. No sudo, no broad compose operations.
set -Eeuo pipefail
umask 077
BASE="${AIOPS_AUTODEPLOY_HOME:-/home/aiops/aiops2-auto-deploy}"
BRANCH="${AIOPS_DEPLOY_BRANCH:-deploy/aiops2-stable}"
# The poller itself must enforce the reviewed ref, even if cron is invoked
# directly with an overridden environment after installation.
if [[ "$BRANCH" != "deploy/aiops2-stable" ]]; then
  echo "BLOCKED: poller only accepts deploy/aiops2-stable" >&2
  exit 1
fi
REMOTE="${AIOPS_DEPLOY_REMOTE:-git@github.com:alimtalbi-ata/aiops.git}"
mkdir -p "$BASE"
exec 9>"$BASE/poll.lock"
flock -n 9 || exit 0

if [[ -e "$BASE/DEPLOYMENT_BLOCKED" ]]; then
  echo "CRITICAL: deployment blocked; manual intervention required" >&2
  exit 1
fi

cd "$BASE"
if [[ ! -d repo/.git ]]; then
  git clone --filter=blob:none "$REMOTE" repo
fi
cd repo
git fetch --no-tags origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
target="$(git rev-parse "refs/remotes/origin/$BRANCH^{commit}")"
applied="$(cat "$BASE/applied.sha" 2>/dev/null || true)"
[[ "$target" != "$applied" ]] || exit 0

# Quarantine a revision that previously failed deployment.
if [[ -f "$BASE/failed.sha" ]] &&
   [[ "$(cat "$BASE/failed.sha")" == "$target" ]]; then
  echo "BLOCKED: revision previously failed: $target" >&2
  exit 1
fi

# Refuse bootstrap without an independently provisioned applied.sha.
if [[ ! "$applied" =~ ^[0-9a-f]{40}$ ]]; then
  echo "BLOCKED: missing or invalid applied.sha; manual bootstrap required" >&2
  exit 1
fi
if ! git cat-file -e "$applied^{commit}" 2>/dev/null; then
  echo "BLOCKED: applied commit unavailable locally" >&2
  exit 1
fi
if ! git merge-base --is-ancestor "$applied" "$target"; then
  echo "BLOCKED: non-fast-forward stable history" >&2
  exit 1
fi

# The current deployer transports ONLY demo_v2.py and its test. It does not
# transport Core/Twin/Copilot/Policy/SQL or a complete portal/main.py.
# Check actual NUL-separated Git changes before checkout/deployment.
diff_file="$(mktemp "$BASE/.approved-diff.XXXXXX")"
trap 'rm -f "$diff_file"' EXIT
if ! git diff --name-status -z --no-renames "$applied" "$target" > "$diff_file"; then
  echo "BLOCKED: cannot inspect candidate file changes" >&2
  exit 1
fi
changed_count=0
while IFS= read -r -d '' status && IFS= read -r -d '' path; do
  ((changed_count+=1))
  if [[ "$status" != A && "$status" != M ]] ||
     [[ -z "$path" ]] || [[ "$path" =~ [[:cntrl:]] ]]; then
    echo "BLOCKED: unsafe candidate diff status or path" >&2
    exit 1
  fi
  case "$path" in
    app/portal/demo_v2.py|tests/test_demo_v2.py|tests/*|docs/*|.github/*|README.md|VERSION|.gitignore) ;;
    *)
      echo "BLOCKED: changed file is not transported by portal-only deployer" >&2
      exit 1
      ;;
  esac
done < "$diff_file"
if (( changed_count == 0 )); then
  echo "BLOCKED: empty candidate diff" >&2
  exit 1
fi
# Fail closed: no forced checkout on a dirty working tree.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: dedicated checkout has local changes; refusing" >&2
  exit 1
fi
git checkout -B aiops2-approved-deployment "$target"
# Approval is the protected branch itself, not a file inside an unreviewed PR.
test -f deploy/deploy-demo-studio-v2.sh
echo "Approved update: $applied -> $target"
if ! bash deploy/deploy-demo-studio-v2.sh; then
  printf '%s\n' "$target" > "$BASE/failed.sha"
  echo "FAILED: revision quarantined: $target" >&2
  exit 1
fi
printf '%s\n' "$target" > "$BASE/applied.sha.tmp"
mv "$BASE/applied.sha.tmp" "$BASE/applied.sha"
echo "Deployment successful: $target"
