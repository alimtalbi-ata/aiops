#!/usr/bin/env bash
# Read-only source recovery and heuristic analysis for the historical AIOps portal.
# Author: Abdelhalim Talbi
# Run with: bash /home/aiops/recovery/tools/collect-historical-portal.sh
# Never source this file into an interactive shell.
set -Eeuo pipefail
umask 077

RECOVERY_ROOT="\${RECOVERY_ROOT:-/home/aiops/recovery/AIOPS-HISTORICAL-PORTAL-20261019-130658}"
R33_SOURCE="\${R33_SOURCE:-/home/aiops/exports/AIOPS-R33-LOGICAL-20261007-112249/03-SOURCES/V1/stack/live_console}"
OUT_ROOT="\${OUT_ROOT:-/home/aiops/recovery/exports}"
V1_EXPORT="\${V1_EXPORT:-$RECOVERY_ROOT/containers/aiops_v1_live_console.tar}"
V145_EXPORT="\${V145_EXPORT:-$RECOVERY_ROOT/containers/aiops_v1_live_console_v145_test.tar}"
STAMP="$(date +%Y%m%d-%H%M%S)"

die() { printf 'ERROR: %s\n' "$*" >&2; return 1; }
need_file() { [[ -f "$1" ]] || { die "Required file missing: $1"; return 1; }; }

mkdir -p "$OUT_ROOT"
STAGE="$(mktemp -d "$OUT_ROOT/.portal-recovery-$STAMP.XXXXXX")"
cleanup() {
  local rc=$?
  if [[ -n "\${STAGE:-}" && -d "$STAGE" ]]; then
    if [[ "$rc" -eq 0 ]]; then rm -rf -- "$STAGE"
    else
      printf 'STAGING_PRESERVED=%s\n' "$STAGE" >&2
      printf 'NOTE=No active containers were changed.\n' >&2
    fi
  fi
}
trap cleanup EXIT

need_file "$R33_SOURCE/app/main.py"
need_file "$R33_SOURCE/requirements.txt"
need_file "$V1_EXPORT"
need_file "$V145_EXPORT"
command -v tar >/dev/null || { die "tar is required"; exit 2; }
command -v sha256sum >/dev/null || { die "sha256sum is required"; exit 2; }
command -v python3 >/dev/null || { die "python3 is required"; exit 2; }
tar -tf "$V1_EXPORT" >/dev/null
tar -tf "$V145_EXPORT" >/dev/null

mkdir -p "$STAGE/R33/live_console" "$STAGE/V1-export/live_console" \
  "$STAGE/V145-export/live_console" "$STAGE/diff" "$STAGE/reports"

FILES=(app/main.py requirements.txt Dockerfile app/static/aiops-portal.html
 app/static/app.js app/static/campaign-studio.html app/static/campaign-studio.js
 app/static/demo-director.html app/static/demo-studio-v2.html
 app/static/demo-videos.html app/static/index.html app/static/styles.css)
for rel in "\${FILES[@]}"; do
  src="$R33_SOURCE/$rel"
  if [[ -f "$src" ]]; then
    mkdir -p "$STAGE/R33/live_console/$(dirname "$rel")"
    install -m 0644 "$src" "$STAGE/R33/live_console/$rel"
  fi
done

extract_selected() {
  local archive="$1" dest="$2" rel normalized
  local found=()
  while IFS= read -r rel; do
    case "$rel" in
      app/app/main.py|app/app/static/aiops-portal.html|app/app/static/app.js|app/app/static/campaign-studio.html|app/app/static/campaign-studio.js|app/app/static/demo-director.html|app/app/static/demo-studio-v2.html|app/app/static/demo-videos.html|app/app/static/index.html|app/app/static/styles.css)
        found+=("$rel") ;;
    esac
  done < <(tar -tf "$archive")
  (("\${#found[@]}" > 0)) || { die "No whitelisted portal files in $archive"; return 1; }
  tar -xf "$archive" -C "$dest" "\${found[@]}"
  for rel in "\${found[@]}"; do
    normalized="\${rel#app/app/}"
    mkdir -p "$dest/live_console/$(dirname "$normalized")"
    install -m 0644 "$dest/$rel" "$dest/live_console/$normalized"
  done
  rm -rf -- "$dest/app"
}
extract_selected "$V1_EXPORT" "$STAGE/V1-export"
extract_selected "$V145_EXPORT" "$STAGE/V145-export"
[[ -s "$STAGE/R33/live_console/app/main.py" ]] || { die "R33 app/main.py missing"; exit 3; }
[[ -s "$STAGE/V1-export/live_console/main.py" ]] || { die "V1 main.py missing"; exit 3; }
[[ -s "$STAGE/V145-export/live_console/main.py" ]] || { die "V145 main.py missing"; exit 3; }

set +e
diff -ru "$STAGE/V1-export/live_console" "$STAGE/V145-export/live_console" > "$STAGE/diff/V1-vs-V145.diff"
d1=$?
diff -ru "$STAGE/R33/live_console" "$STAGE/V145-export/live_console" > "$STAGE/diff/R33-vs-V145.diff"
d2=$?
set -e
((d1 <= 1 && d2 <= 1)) || { die "diff failed"; exit 4; }

python3 - "$STAGE" <<'PY'
from pathlib import Path
import hashlib, re, sys
root=Path(sys.argv[1]); inventory=root/"reports/SOURCE-INVENTORY.tsv"; report=root/"reports/STATIC-ANALYSIS.txt"
text_ext={".py",".js",".html",".css",".txt",".yml",".yaml",".json",".md"}
patterns=[
 (r"\bTODO\b|\bFIXME\b|\bXXX\b","TODO/FIXME marker"),
 (r"\bexcept\s*:\s*$","bare except"),
 (r"\beval\s*\(","eval() usage"),
 (r"\binnerHTML\s*=","innerHTML assignment: review escaping"),
 (r"verify\s*=\s*False","TLS verification disabled"),
 (r"(?:password|secret|api[_-]?key|token)\s*=\s*['\"][^'\"]{8,}['\"]","possible hard-coded credential: manual review"),
]
rows=[]; findings=[]
for p in sorted(root.rglob("*")):
 if not p.is_file(): continue
 rel=p.relative_to(root).as_posix(); data=p.read_bytes()
 rows.append((rel,len(data),hashlib.sha256(data).hexdigest()))
 if p.suffix.lower() not in text_ext: continue
 lines=data.decode("utf-8",errors="replace").splitlines()
 findings.append(f"{rel}: bytes={len(data)} lines={len(lines)} sha256={hashlib.sha256(data).hexdigest()}")
 for n,line in enumerate(lines,1):
  for pattern,label in patterns:
   if re.search(pattern,line,re.I): findings.append(f"  REVIEW {label} line={n}: {line.strip()[:180]}")
inventory.write_text("path\tbytes\tsha256\n"+"".join(f"{a}\t{b}\t{c}\n" for a,b,c in rows),encoding="utf-8")
report.write_text("AIOps historical portal — heuristic static analysis\nAuthor: Abdelhalim Talbi\nScope: whitelisted source only; manual verification required.\nNot performed: runtime, dependency install, API/E2E or browser tests.\n\n"+"\n".join(findings)+f"\n\nFILES_IN_INVENTORY={len(rows)}\n",encoding="utf-8")
PY

cat > "$STAGE/RECOVERY-MANIFEST.txt" <<EOF
AIOps historical portal source recovery and static analysis
Author: Abdelhalim Talbi
Created: $(date -Is)
Host: $(hostname)
Evidence: selective source extraction, SHA-256 inventory, heuristic static analysis and textual diffs.
No runtime qualification is implied.
Inputs:
- R33: $R33_SOURCE
- V1 export: $V1_EXPORT
- V145 export: $V145_EXPORT
Included:
- Whitelisted source files from R33, V1 and V145
- V1-vs-V145 and R33-vs-V145 diffs
- Static analysis and source inventory
Excluded:
- .env, credentials, database files, volumes, logs, caches, bytecode and full container layers
- Active container or application-data changes
Invariant: do not alter PC11K5 fencing/ownership behavior during historical recovery.
EOF

if find "$STAGE" -type f \( -name '.env' -o -name '.env.*' -o -iname '*credential*' -o -iname '*private-key*' \) -print -quit | grep -q .; then
  die "Secret-like filename in staging; refusing to package"
fi
(cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
PACKAGE="$OUT_ROOT/AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-$STAMP.tar.gz"
tar -czf "$PACKAGE" -C "$STAGE" .
chmod 600 "$PACKAGE"
sha256sum "$PACKAGE" > "$PACKAGE.sha256"
chmod 600 "$PACKAGE.sha256"
sha256sum -c "$PACKAGE.sha256"
tar -tzf "$PACKAGE" >/dev/null
printf 'PACKAGE=%s\nCHECKSUM_FILE=%s.sha256\n' "$PACKAGE" "$PACKAGE"
printf 'PACKAGE_SIZE=%s bytes\n' "$(stat -c %s "$PACKAGE")"
printf 'V1_V145_DIFF_LINES=%s\n' "$(wc -l < "$STAGE/diff/V1-vs-V145.diff")"
printf 'R33_V145_DIFF_LINES=%s\n' "$(wc -l < "$STAGE/diff/R33-vs-V145.diff")"
printf 'INVENTORY_ROWS=%s\n' "$(( $(wc -l < "$STAGE/reports/SOURCE-INVENTORY.tsv") - 1 ))"
printf 'RESULT=SOURCE_RECOVERY_AND_STATIC_REPORT_CREATED_NO_RUNTIME_CHANGES\n'
