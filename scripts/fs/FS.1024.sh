#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1024 | CAPTURE DEPLOYED TWIN SOURCE + VERSION CORE COMPOSE OVERLAY ====='
[[ "${1:---plan}" == --plan || "${1:---plan}" == --publish ]] || { echo 'USAGE: FS.1024.sh --plan|--publish'; exit 2; }
MODE="${1:---plan}"
REPO=/home/aiops/aiops2-v2-delivery
BRANCH=fix/fs-1009-twin-decimal-metrics
TWIN=aiops2-rebuild-twin
CORE=aiops2-rebuild-core
TWIN_IMAGE=aiops2-twin:fs1009-decimal-metrics-candidate-20261106
CORE_IMAGE=aiops2-core:fs1017-metrics-candidate-20261106
TWIN_SHA=2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb
CORE_ID=sha256:c31c2412af358fe93c680fa8f7193307c5b316aaba57a4b31b42296304818d67
F1=/home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml
F2=/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml
test -d "$REPO/.git"
test -f "$F1" && test -f "$F2"
test "$(docker inspect --format '{{.Image}}' "$CORE")" = "$CORE_ID"
test "$(docker inspect --format '{{.State.Running}}' "$TWIN")" = true
test "$(docker inspect --format '{{.State.Running}}' "$CORE")" = true
test "$(docker inspect --format '{{.Image}}' "$TWIN")" = "$(docker image inspect --format '{{.Id}}' "$TWIN_IMAGE")"
docker image inspect "$CORE_IMAGE" >/dev/null
TMP="$(mktemp -d /tmp/fs1024.XXXXXXXX)"
chmod 700 "$TMP"
cleanup(){ git -C "$REPO" worktree remove --force "$TMP/worktree" >/dev/null 2>&1 || true; rm -rf "$TMP"; }
trap cleanup EXIT
mkdir -p "$TMP/extract"
docker cp "$TWIN:/app/twin/fs_observations.py" "$TMP/extract/fs_observations.py" >/dev/null
test "$(sha256sum "$TMP/extract/fs_observations.py" | awk '{print $1}')" = "$TWIN_SHA" || { echo 'NO_GO=DEPLOYED_TWIN_SOURCE_SHA_MISMATCH'; exit 1; }
python3 - "$TMP/extract/fs_observations.py" <<'PY'
import ast,sys
p=sys.argv[1];s=open(p,encoding='utf-8').read();ast.parse(s)
assert 'def _validated_fs_percent(' in s
assert 'Decimal' in s
assert 'math.isfinite' in s
assert 'fs_lab_metrics' in s
print('DEPLOYED_TWIN_SOURCE=VERIFIED')
PY
echo "TWIN_SOURCE_SHA256=$TWIN_SHA"
echo '===== VERIFY PERSISTENT CORE COMPOSE ALIGNED ====='
(cd /home/aiops/aiops-prometheus-image-patch && docker compose -p aiops2-metrics-cutover -f "$F1" -f "$F2" config --format json) | python3 -c '
import json,sys
s=json.load(sys.stdin)["services"]["aiops2-core"]
assert s["image"]=="aiops2-core:fs1017-metrics-candidate-20261106"
print("HOST_COMPOSE_IMAGE=ALIGNED")
'
git -C "$REPO" fetch origin "$BRANCH"
git -C "$REPO" worktree add --detach "$TMP/worktree" "origin/$BRANCH" >/dev/null
test ! -e "$TMP/worktree/app/twin/fs_observations.py" || { echo 'NO_GO=SOURCE_ALREADY_VERSIONED'; exit 1; }
mkdir -p "$TMP/worktree/app/twin" "$TMP/worktree/deploy"
cp "$TMP/extract/fs_observations.py" "$TMP/worktree/app/twin/fs_observations.py"
cat > "$TMP/worktree/deploy/compose.core-metrics-image.yml" <<'YAML'
# FS.1024: explicit image pin for Core; use with the two existing host Compose files.
# No credentials, network changes, or container recreation are embedded here.
services:
  aiops2-core:
    image: aiops2-core:fs1017-metrics-candidate-20261106
YAML
cat > "$TMP/worktree/deploy/FS.1024-README.md" <<'MD'
# FS.1024 — Reproducible source / Core image pin

- `app/twin/fs_observations.py` was copied **unchanged** from the deployed Twin container after verifying SHA256 `2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb`.
- `deploy/compose.core-metrics-image.yml` is a versioned **third Compose override** that pins the deployed Core candidate image. It does not replace or capture the complete host-side override at `/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml`.
- When managing Core from the host, use `docker compose -p aiops2-metrics-cutover -f /home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml -f /home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml -f deploy/compose.core-metrics-image.yml config` to inspect the merged configuration; **do not run up** without separate approval.
- The exact production Twin candidate was built by overlaying the runtime module onto an earlier Twin image. The Dockerfile for a clean-source Twin build still needs a separate qualification before this can be described as a fully reproducible production image.
- Core/Twin were UP during FS.1021. This file does not claim ongoing monitoring or CI validation.
MD
python3 - "$TMP/worktree/app/twin/fs_observations.py" <<'PY'
import pathlib,sys
s=pathlib.Path(sys.argv[1]).read_text()
for marker in ('BEGIN PRIVATE KEY','ghp_','github_pat_','DATABASE_URL=','ADMIN_TOKEN=','AIOPS_INTERNAL_TOKEN='):
 assert marker not in s,'NO_GO=SENSITIVE_LITERAL_DETECTED'
print('SOURCE_LITERAL_SAFETY_SCAN=PASS')
PY
git -C "$TMP/worktree" diff --no-index -- /dev/null "$TMP/worktree/app/twin/fs_observations.py" > "$TMP/source.diff" || [[ "$?" == 1 ]]
echo 'FS1024_PREPARED=PASS'
if [[ "$MODE" == --plan ]]; then
 echo 'FS1024_RESULT=PLAN_PASS_NO_PUSH'
 exit 0
fi
[[ "${FS1024_APPROVE_GITHUB_PUBLISH:-}" == YES ]] || { echo 'NO_GO=GITHUB_PUBLISH_APPROVAL_REQUIRED'; exit 2; }
git -C "$TMP/worktree" add -- app/twin/fs_observations.py deploy/compose.core-metrics-image.yml deploy/FS.1024-README.md
git -C "$TMP/worktree" -c user.name='AIOps FS automation' -c user.email='aiops-fs@users.noreply.github.com' commit -m 'fix(fs1024): version deployed Twin exporter and Core image Compose pin' >/dev/null
echo '===== PUBLISH TO EXISTING REVIEW BRANCH (FAST FORWARD ONLY) ====='
git -C "$TMP/worktree" push origin "HEAD:refs/heads/$BRANCH"
echo "FS1024_COMMIT=$(git -C "$TMP/worktree" rev-parse HEAD)"
echo 'PRODUCTION_CONTAINERS_CHANGED=NO'
echo 'HOST_COMPOSE_FILES_CHANGED=NO'
echo 'FS1024_RESULT=PUBLISHED'
