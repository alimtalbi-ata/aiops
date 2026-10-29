#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=/home/aiops
DEST="$ROOT/aiops2-reconstruction-export-20261029"
ACTIVE="$ROOT/aiops2-p0-consolidation"
HIST="$ROOT/aiops2-v2-delivery"
REC="$ROOT/aiops2-itsm-historical-recovery-20261029"
CAND="$ROOT/aiops2-itsm-portal-candidate-20261029"

command -v git >/dev/null
command -v tar >/dev/null
command -v docker >/dev/null
command -v python3 >/dev/null

if [ -e "$DEST" ]; then
  echo "ARRET : destination existante : $DEST"
  exit 1
fi

mkdir -p "$DEST"/{sources,scripts,inventory,git-history,db-exports,docs}

echo "=== COPIE DES SOURCES ==="

copy_tree() {
  local src="$1"
  local name="$2"

  if [ ! -d "$src" ]; then
    echo "ABSENT : $src"
    return
  fi

  mkdir -p "$DEST/sources/$name"

  tar -C "$src" \
    --exclude='./.git' \
    --exclude='./.env' \
    --exclude='./.env.*' \
    --exclude='*.pem' \
    --exclude='*.key' \
    --exclude='id_rsa*' \
    --exclude='id_ed25519*' \
    --exclude='*.sqlite' \
    --exclude='*.sqlite3' \
    --exclude='*.db' \
    --exclude='*.sql' \
    --exclude='*.dump' \
    --exclude='*.bak' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='*.log' \
    -cf - . |
    tar -C "$DEST/sources/$name" -xf -

  echo "COPIE : $name"
}

copy_tree "$ACTIVE" active
copy_tree "$HIST" historical
copy_tree "$REC" recovered
copy_tree "$CAND" candidate

echo
echo "=== HISTORIQUE GIT ==="

for spec in "active:$ACTIVE" "historical:$HIST"; do
  name="${spec%%:*}"
  dir="${spec#*:}"

  if git -C "$dir" rev-parse --is-inside-work-tree \
      >/dev/null 2>&1; then
    git -C "$dir" rev-parse HEAD \
      > "$DEST/inventory/${name}-commit.txt"

    git -C "$dir" bundle create \
      "$DEST/git-history/${name}.bundle" --all

    echo "BUNDLE : $name"
  fi
done

echo
echo "=== SCRIPTS DE RECUPERATION ==="

find /tmp -maxdepth 1 -type f \
  \( -name 'aiops2-*.sh' -o -name '*itsm*.sh' \) \
  -exec cp -n {} "$DEST/scripts/" \;

echo
echo "=== INVENTAIRE DOCKER ==="

docker ps -a \
  --format '{{.Names}} | {{.Image}} | {{.Status}}' \
  > "$DEST/inventory/containers.txt"

docker volume ls --format '{{.Name}}' \
  > "$DEST/inventory/volumes.txt"

docker images \
  --format '{{.Repository}}:{{.Tag}} | {{.ID}}' \
  > "$DEST/inventory/images.txt"

docker network ls \
  --format '{{.Name}} | {{.Driver}}' \
  > "$DEST/inventory/networks.txt"

echo
echo "=== MANIFESTE DES FICHIERS ==="

(
  cd "$DEST"
  find sources scripts git-history -type f | sort |
    while IFS= read -r file; do
      sha256sum "$file"
    done
) > "$DEST/inventory/SHA256SUMS.txt"

cat > "$DEST/docs/README.md" <<'EOF'
# AIOps2 — Kit de reconstruction

Date du checkpoint : 2026-10-29

## Contenu

- sources/active : code actif AIOps2
- sources/historical : ancien dépôt
- sources/recovered : modules historiques récupérés
- sources/candidate : Portal candidat non déployé
- scripts : scripts de diagnostic et de qualification
- git-history : historique Git exporté
- inventory : inventaire Docker et empreintes SHA-256
- db-exports : emplacement réservé aux exports synthétiques

## État vérifié

- Core / Worker : fonctionnement fail-closed précédemment validé
- GLPI Reader : 24 tests unitaires réussis
- ITSM : 23 tests réussis, 1 échec
- HITL : 56 tests réussis, 11 échecs
- Console : 11 tests réussis, 4 échecs
- Portal candidat : tests bloqués par glpi_reader absent
- n8n : workflow ACME dry-run confirmé
- GLPI REST réel et création de tickets : non validés
- Bot historique : récupération non terminée

## Reconstruction

1. Restaurer le dépôt et consulter les historiques Git.
2. Vérifier Dockerfiles, Compose, variables d'environnement et volumes.
3. Recréer les bases à partir des migrations et fixtures.
4. Restaurer les exports de données synthétiques si disponibles.
5. Construire les images et démarrer les services en environnement isolé.
6. Exécuter les tests GLPI, ITSM, HITL, Console, Core et Worker.
7. Vérifier RBAC, isolation tenant et politique fail-closed.

ATTENTION : ce kit n'est pas encore une restauration intégrale validée.
Les dumps de bases et les contenus des volumes doivent être exportés
et testés séparément.
EOF

cat > "$DEST/.gitignore" <<'EOF'
.env
.env.*
!.env.example
*.pem
*.key
id_rsa*
id_ed25519*
*.sqlite
*.sqlite3
*.db
*.sql
*.dump
*.bak
*.log
__pycache__/
*.pyc
.venv/
venv/
node_modules/
db-exports/*
!db-exports/README.md
EOF

cat > "$DEST/db-exports/README.md" <<'EOF'
# Exports des bases

À compléter après identification du moteur et des volumes.
Ne pas utiliser de copie brute de fichiers d'une base active.
Préférer les dumps cohérents et une restauration testée.

Les exports synthétiques vérifiés peuvent ensuite être ajoutés
explicitement au dépôt, après contrôle de leur contenu.
EOF

echo
echo "=== CONTROLE DES SECRETS ==="

python3 - "$DEST" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
patterns = [
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)(password|passwd|secret|api_key|access_token)\s*[:=]\s*['\"]?[A-Za-z0-9+/=_-]{12,}"),
]
hits = []
for path in root.rglob("*"):
    if not path.is_file() or ".git" in path.parts:
        continue
    if path.suffix in {".bundle", ".png", ".jpg", ".zip", ".gz"}:
        continue
    if path.stat().st_size > 2_000_000:
        continue
    try:
        data = path.read_text(encoding="utf-8")
    except (UnicodeError, OSError):
        continue
    if any(p.search(data) for p in patterns):
        hits.append(str(path.relative_to(root)))

if hits:
    print("CONTROLE BLOQUANT : fichiers à examiner :")
    for name in hits:
        print(" -", name)
    sys.exit(2)

print("Contrôle indicatif terminé ; revue humaine encore nécessaire.")
PY

echo
echo "=== PREPARATION GIT ==="

cd "$DEST"
git init -b recovery-20261029
git add .
git commit -m "checkpoint: reconstruction AIOps2 2026-10-29"

echo
echo "=== PUBLICATION GITHUB ==="

if [ -n "${GITHUB_REPO:-}" ]; then
  command -v gh >/dev/null || {
    echo "gh absent : publication non effectuée"
    exit 0
  }

  visibility=$(gh repo view "$GITHUB_REPO" \
    --json visibility --jq '.visibility') || exit 1

  if [ "$visibility" != "PRIVATE" ]; then
    echo "ARRET : dépôt GitHub non privé"
    exit 1
  fi

  git remote add origin \
    "https://github.com/${GITHUB_REPO}.git"

  git push -u origin recovery-20261029

  echo "PUBLICATION EFFECTUEE : $GITHUB_REPO"
else
  echo "EXPORT LOCAL TERMINE."
  echo "Pour publier, relancer avec GITHUB_REPO=owner/repo"
  echo "Attention : ne pas relancer ce script sur la même destination."
fi

echo
echo "DOSSIER : $DEST"
