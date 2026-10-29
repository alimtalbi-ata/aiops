#!/usr/bin/env bash
set -Eeuo pipefail

# One-command deployment of isolated AIOps2 demo observability.
# Execute on SRV-DEB-05 as rootless Docker user aiops.
REPO_URL="https://github.com/alimtalbi-ata/aiops.git"
BRANCH="feat/observability-loki-tempo-otel-20261029"
EXPECTED_SHA="28602848e4f2465fd98776670a14c52d6bcf81d2"
PROJECT="aiops2-demo-observability"
NETWORK="aiops2-rebuild-observability"
INSTALL_DIR="${HOME}/aiops2-observability-deploy"
SRC_DIR="${INSTALL_DIR}/deploy/observability-demo"
IMAGES=("grafana/loki:3.5.0" "grafana/tempo:2.7.2" "otel/opentelemetry-collector-contrib:0.123.0")
SERVICES=("demo-loki" "demo-tempo" "demo-otel")
tmp=""
cleanup() { [[ -z "${tmp}" ]] || rm -rf "${tmp}"; }
trap cleanup EXIT
die() { printf 'ERREUR: %s\n' "$*" >&2; exit 1; }
say() { printf '\n==> %s\n' "$*"; }

[[ "$(id -u)" -ne 0 ]] || die "Ne pas exécuter en root; Docker rootless attendu."
command -v git >/dev/null || die "git manquant"
command -v docker >/dev/null || die "docker manquant"
docker info >/dev/null 2>&1 || die "Docker inaccessible"
docker compose version >/dev/null || die "docker compose manquant"
docker network inspect "${NETWORK}" >/dev/null 2>&1 || die "Réseau ${NETWORK} absent"
[[ ! -e "${INSTALL_DIR}" ]] || die "${INSTALL_DIR} existe déjà. Aucun écrasement automatique."
if docker ps -a --format '{{.Names}}' | grep -Eq '^aiops2-demo-observability-(demo-loki|demo-tempo|demo-otel)-1$'; then
  die "Conteneurs candidats déjà présents; vérifier manuellement avant de poursuivre."
fi

say "Téléchargement de la configuration figée ${EXPECTED_SHA}"
tmp="$(mktemp -d)"
git -C "${tmp}" init -q
git -C "${tmp}" remote add origin "${REPO_URL}"
git -C "${tmp}" fetch --no-tags --depth=1 origin "${EXPECTED_SHA}"
actual="$(git -C "${tmp}" rev-parse FETCH_HEAD)"
[[ "${actual}" == "${EXPECTED_SHA}" ]] || die "SHA de branche différent (${actual}); candidat modifié, déploiement arrêté"
git -C "${tmp}" archive FETCH_HEAD deploy/observability-demo | tar -xf - -C "${tmp}"
[[ -f "${tmp}/deploy/observability-demo/compose.yml" ]] || die "Compose candidat introuvable"

say "Prévalidation Compose (aucune modification des services existants)"
(cd "${tmp}/deploy/observability-demo" && docker compose -p "${PROJECT}" -f compose.yml config -q)
for img in "${IMAGES[@]}"; do
  say "Récupération image ${img}"
  docker pull "${img}"
done

# Install only after all checks and image pulls succeed.
mkdir -m 700 "${INSTALL_DIR}"
cp -a "${tmp}/deploy" "${INSTALL_DIR}/"
cd "${SRC_DIR}"
say "Démarrage isolé du projet ${PROJECT}"
docker compose -p "${PROJECT}" -f compose.yml up -d --no-build --pull never

say "État des conteneurs"
docker compose -p "${PROJECT}" -f compose.yml ps
say "Contrôle de stabilité (15 secondes)"
sleep 15
for svc in "${SERVICES[@]}"; do
  cid="$(docker compose -p "${PROJECT}" -f compose.yml ps -q "${svc}")"
  [[ -n "${cid}" ]] || die "Conteneur ${svc} absent"
  status="$(docker inspect "${cid}" --format '{{.State.Status}}')"
  [[ "${status}" == "running" ]] || die "${svc} n'est pas running (status=${status})"
done
say "Démarrage confirmé; endpoints et ingestion OTLP restent à tester avant GO."
printf 'Installation: %s\nRévision: %s\n' "${INSTALL_DIR}" "${EXPECTED_SHA}"
printf 'Rollback sans suppression de volumes: cd %q && docker compose -p %q -f compose.yml down\n' "${SRC_DIR}" "${PROJECT}"
