#!/usr/bin/env bash
# Read-only source recovery for the historical AIOps v1/V145 portal.
# Author: Abdelhalim Talbi
set -Eeuo pipefail
umask 077

RECOVERY_ROOT="${RECOVERY_ROOT:-/home/aiops/recovery/AIOPS-HISTORICAL-PORTAL-20261019-130658}"
R33_SOURCE="${R33_SOURCE:-/home/aiops/exports/AIOPS-R33-LOGICAL-20261007-112249/03-SOURCES/V1/stack/live_console}"
V1_EXPORT="$RECOVERY_ROOT/containers/aiops_v1_live_console.tar"
V145_EXPORT="$RECOVERY_ROOT/containers/aiops_v1_live_console_v145_test.tar"
OUT_ROOT="${OUT_ROOT:-/home/aiops/recovery/exports}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT_ROOT"
STAGE="$(mktemp -d "$OUT_ROOT/.portal-recovery-$STAMP.XXXXXX")"
trap 'rm -rf -- "$STAGE"' EXIT

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need_file() { [[ -f "$1" ]] || die "Required file missing: $1"; }
need_file "$R33_SOURCE/main.py"
need_file "$R33_SOURCE/requirements.txt"
need_file "$V1_EXPORT"
need_file "$V145_EXPORT"
mkdir -p "$OUT_ROOT" "$STAGE/R33/live_console" "$STAGE/V1-export" "$STAGE/V145-export" "$STAGE/diff"

# Whitelist only source/runtime files needed to rebuild and compare the portal.
FILES=(
  main.py requirements.txt Dockerfile
  app/static/aiops-portal.html
  app/static/app.js
  app/static/campaign-studio.html
  app/static/campaign-studio.js
  app/static/demo-director.html
  app/static/demo-studio-v2.html
  app/static/demo-videos.html
  app/static/index.html
  app/static/styles.css
)

for rel in "${FILES[@]}"; do
  src="$R33_SOURCE/$rel"
  if [[ -f "$src" ]]; then
    mkdir -p "$STAGE/R33/live_console/$(dirname "$rel")"
    install -m 0644 "$src" "$STAGE/R33/live_console/$rel"
  fi
done

# Selective extraction from container exports: no image layers, DBs, volumes,
# runtime secrets, logs, caches, or *.bak files are included.
TAR_PATHS=(
  app/app/main.py
  app/app/static/aiops-portal.html
  app/app/static/app.js
  app/app/static/campaign-studio.html
  app/app/static/campaign-studio.js
  app/app/static/demo-director.html
  app/app/static/demo-studio-v2.html
  app/app/static/demo-videos.html
  app/app/static/index.html
  app/app/static/styles.css
)
extract_selected() {
  local archive="$1" dest="$2"
  local found=()
  local rel
  while IFS= read -r rel; do
    case "$rel" in
      app/app/main.py|app/app/static/aiops-portal.html|app/app/static/app.js|app/app/static/campaign-studio.html|app/app/static/campaign-studio.js|app/app/static/demo-director.html|app/app/static/demo-studio-v2.html|app/app/static/demo-videos.html|app/app/static/index.html|app/app/static/styles.css)
        found+=("$rel")
        ;;
    esac
  done < <(tar -tf "$archive")
  (("${#found[@]}" > 0)) || die "No whitelisted source files found in $archive"
  tar -xf "$archive" -C "$dest" "${found[@]}"
  # Normalize container-export paths to a predictable source layout.
  mkdir -p "$dest/live_console"
  [[ ! -d "$dest/app/app" ]] || cp -a "$dest/app/app/." "$dest/live_console/"
  rm -rf -- "$dest/app"
}
extract_selected "$V1_EXPORT" "$STAGE/V1-export"
extract_selected "$V145_EXPORT" "$STAGE/V145-export"

# Create a compact comparison report. Differences are leads for review, not
# proof that one version is correct or qualified.
diff -ru "$STAGE/V1-export/live_console" "$STAGE/V145-export/live_console" \
  > "$STAGE/diff/V1-vs-V145.diff" || diff_status=$?
diff_status="${diff_status:-0}"
if (( diff_status > 1 )); then die "diff failed with status $diff_status"; fi

cat > "$STAGE/RECOVERY-MANIFEST.txt" <<EOF
AIOps historical portal source recovery
Author: Abdelhalim Talbi
Created: $(date -Is)
Host: $(hostname)
Purpose: preserve source candidates for selective reuse in AIOps 2.0
Evidence level: source extraction and textual comparison only; no runtime qualification implied.

Inputs:
- R33 source: $R33_SOURCE
- v1 container export: $V1_EXPORT
- V145 test container export: $V145_EXPORT

Included:
- Whitelisted portal source files from R33
- Whitelisted source files selectively extracted from v1 and V145 exports
- Text diff V1-vs-V145

Excluded intentionally:
- .env and all secrets/tokens/credentials
- database files, Docker volumes, container writable layers beyond selected source paths
- logs, caches, bytecode, PID files, and *.bak files
- V92 container export (previously observed export was only 1024 bytes; image metadata was unavailable)

Qualification status:
- Source preservation only.
- API compatibility, dependency closure, build, UI behavior, and E2E remain to be verified.
- PC11K5 fencing invariants must not be changed by this recovery.
EOF

# Do not package any unexpected environment or secret files.
if find "$STAGE" -type f \( -name '.env' -o -name '.env.*' -o -iname '*secret*' -o -iname '*token*' -o -iname '*credential*' \) -print -quit | grep -q .; then
  die "Potential secret-named file found in staging; refusing to package"
fi
(
  cd "$STAGE"
  find . -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
mkdir -p "$OUT_ROOT"
PACKAGE="$OUT_ROOT/AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-$STAMP.tar.gz"
tar -czf "$PACKAGE" -C "$STAGE" .
chmod 600 "$PACKAGE"
sha256sum "$PACKAGE" > "$PACKAGE.sha256"
chmod 600 "$PACKAGE.sha256"

printf 'PACKAGE=%s\n' "$PACKAGE"
printf 'CHECKSUM_FILE=%s.sha256\n' "$PACKAGE"
printf 'PACKAGE_SIZE=%s bytes\n' "$(stat -c %s "$PACKAGE")"
printf 'DIFF_LINES=%s\n' "$(wc -l < "$STAGE/diff/V1-vs-V145.diff")"
printf 'SOURCE_FILES=%s\n' "$(find "$STAGE" -type f | wc -l)"
printf 'RESULT=SOURCE_RECOVERY_PACKAGE_CREATED_NO_RUNTIME_CHANGES\n"
