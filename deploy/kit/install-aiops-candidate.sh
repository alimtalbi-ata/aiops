#!/usr/bin/env bash
set -Eeuo pipefail
umask 027
REPO_URL="https://github.com/alimtalbi-ata/aiops.git"
BRANCH="feat/v21310-star-portal-continuity-20261022"
PORTAL_URL="${AIOPS_PORTAL_URL:-http://10.79.94.202:17777/}"
DEST="${AIOPS_CANDIDATE_DIR:-/opt/aiops-candidate}"
MODE=audit
usage(){ cat <<'EOF'
Usage: sudo ./install-aiops-candidate.sh [--audit] [--install] [--dest ABSOLUTE_PATH]
Default --audit is read-only. --install clones/updates isolated candidate source only.
It does not install dependencies, touch Docker/firewall/systemd, mount routes or restart production.
Existing checkouts must be clean; local changes are never reset or overwritten.
EOF
}
while (($#)); do case "$1" in
 --audit) MODE=audit; shift;; --install) MODE=install; shift;;
 --dest) [[ $# -ge 2 ]] || { echo "--dest requires a path" >&2; exit 2; }; DEST="$2"; shift 2;;
 --help|-h) usage; exit 0;; *) echo "Unknown option: $1" >&2; usage >&2; exit 2;;
esac; done
log(){ printf '[AIOPS-INSTALL] %s\n' "$*"; }
fail(){ log "ERROR: $*"; exit 1; }
[[ "$(uname -s)" == Linux ]] || fail "Linux required"
[[ -r /etc/os-release ]] || fail "/etc/os-release missing"
. /etc/os-release
[[ "${ID:-}" == debian || "${ID_LIKE:-}" == *debian* ]] || log "WARNING: target is ${PRETTY_NAME:-unknown}; intended for Debian"
log "Mode=$MODE OS=${PRETTY_NAME:-unknown} user=$(id -un)"
log "Single portal probe only: $PORTAL_URL"
df -h "${DEST%/*}" 2>/dev/null || df -h /
if command -v curl >/dev/null 2>&1; then curl --connect-timeout 3 --max-time 5 -sS -o /dev/null -w 'HTTP %{http_code}; remote=%{remote_ip}; total=%{time_total}s\n' "$PORTAL_URL" || log "WARNING: portal probe failed; no changes attempted"; else log "MISSING: curl"; fi
if command -v docker >/dev/null 2>&1; then docker ps --format 'container={{.Names}} image={{.Image}} ports={{.Ports}}' 2>&1 || log "WARNING: Docker inventory unavailable"; else log "INFO: Docker CLI absent"; fi
if command -v ss >/dev/null 2>&1; then ss -ltn 2>/dev/null || true; fi
if [[ "$MODE" == audit ]]; then log "AUDIT COMPLETE: no changes made"; exit 0; fi
[[ "$DEST" == /* && "$DEST" != "/" && "$DEST" != "/opt" && "$DEST" != "/home" ]] || fail "unsafe destination path: $DEST"
[[ ! -L "$DEST" ]] || fail "destination must not be a symlink: $DEST"
command -v git >/dev/null 2>&1 || fail "git required for --install"
if [[ -e "$DEST" && ! -d "$DEST/.git" ]]; then fail "destination exists but is not a Git checkout; refusing overwrite: $DEST"; fi
if [[ -d "$DEST/.git" ]]; then
 remote="$(git -C "$DEST" remote get-url origin 2>/dev/null || true)"
 [[ "$remote" == "$REPO_URL" ]] || fail "existing checkout origin mismatch: $remote"
 if [[ -n "$(git -C "$DEST" status --porcelain)" ]]; then
   git -C "$DEST" status --short >&2
   fail "existing checkout has local changes; refusing to reset or overwrite them"
 fi
 git -C "$DEST" fetch --depth 1 origin "$BRANCH"
 git -C "$DEST" checkout -B "$BRANCH" FETCH_HEAD
else
 mkdir -p "$(dirname "$DEST")"
 git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$DEST"
fi
[[ "$(git -C "$DEST" branch --show-current)" == "$BRANCH" ]] || fail "candidate branch mismatch after checkout"
git -C "$DEST" rev-parse HEAD | tee "$DEST/INSTALL-COMMIT.txt"
git -C "$DEST" status --short
log "CANDIDATE SOURCE READY: $DEST"
log "Production portal has NOT been changed. Runtime route mounting and E2E qualification remain separate."
