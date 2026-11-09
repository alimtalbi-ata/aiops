# Agent 7 — correctif DR PostgreSQL 16 après e0fc66c3

Parent exact : `e0fc66c3bc8f56cace0074de2f0a07d5bb551303`. Rédacteur unique Agent 7. L'utilisateur lève le gel pour ce seul correctif et rapporte le journal du job 129438966138, run 42699163023 : `SET transaction_timeout = 0` non reconnu par PostgreSQL 16.15. Codex n'a pas relu ce journal via API ; les versions/chemins exacts des anciens clients CI restent inconnus. Le nouveau workflow relève les clients par défaut avant installation, puis le script journalise les clients sélectionnés et le serveur.

## Delta précis

- `.github/workflows/quality.yml` : seul job database-migrations ; installer `postgresql-client-16`, placer `/usr/lib/postgresql/16/bin` dans GITHUB_PATH pour toutes les étapes suivantes, fixer DR_POSTGRES_BINDIR au même chemin. Tous les jobs existants restent présents.
- `tests/postgres-dr-rehearsal.sh` : relever chemin résolu/version des trois clients sélectionnés, exiger le major 16, relever version du serveur et son BINDIR, exiger le major 16 avant dump/restauration. Pas de suppression ni réécriture de SQL.
- Registre d'attribution et preuves documentaires de ce correctif uniquement. Aucun fichier applicatif, migration ou outil de banc modifié.

Le corps initial du test à partir du calcul de ROOT est byte-identique au parent : refus cible préexistante, dump custom, TOC non vide, rejet archive corrompue, restauration `--exit-on-error --single-transaction`, empreintes triées de toutes les lignes, nombre de tables, rapport et nettoyage de la seule base créée sont préservés.

## Vérification réellement exécutée

Banc jetable propre `aiops2-agent7-462-dr-bac525f4`, network none, aucun port publié, données tmpfs ; image locale `aiops2-agent7-462-dr16:qualification` (postgres:16-bookworm avec Python3 pour écrire le rapport). L'ajout Python utilise uniquement les dépôts Debian ; le premier build avait échoué sur le dépôt PGDG inaccessible, qui n'était pas nécessaire pour installer Python. Aucun accès réseau contourné. Migrations complètes #194 et suites SQL ledger/evidence appliquées sur cette base uniquement.

Clients sélectionnés : `/usr/lib/postgresql/16/bin/pg_dump`, `pg_restore`, `psql` : tous PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2). Serveur 16.15, server_version_num 160015, BINDIR déclaré `/usr/lib/postgresql/16/bin` (exécutable PostgreSQL attendu `postgres` dans ce répertoire). Les chemins sont ceux du conteneur de qualification, pas du Debian opérationnel.

Commande : `docker --host=unix:///var/run/docker.sock exec -e DR_POSTGRES_BINDIR=/usr/lib/postgresql/16/bin aiops2-agent7-462-dr-bac525f4 bash -x /qualification/tests/postgres-dr-rehearsal.sh` (sélecteurs Docker hérités retirés du processus).

Résultat : PASS, 32 tables, empreintes MATCH, contrôle archive corrompue PASS, base de restauration supprimée par le test. Un premier passage avec les wrappers par défaut 16.15 avait aussi passé ; la preuve jointe est le second passage avec chemins versionnés explicites, comme en CI.

Contrôle négatif séparé : psql `-v ON_ERROR_STOP=1 -c 'SET transaction_timeout = 0'` contre ce serveur renvoie bien `unrecognized configuration parameter`. L'erreur n'est ni ignorée ni filtrée dans le test corrigé.

Autres vérifications : `bash -n tests/postgres-dr-rehearsal.sh`, `git diff --check`, comparaison automatique du corps de test au parent. Preuves `bench462-postgres16-*`, empreintes dans `bench462-SHA256SUMS`.

## Publication et limites

Un commit distinct sera poussé sur `agent/integration/462-isolated-candidate`, déclenchant le workflow qualité par événement push sur son nouveau SHA ; résultat à relever séparément, sans réattribuer cette CI au parent gelé. Le descriptif de PR préparé est conservé ; aucune nouvelle tentative API. Le correctif ne qualifie aucun système réel : Debian, FS1250 et E2E réels HOLD. Aucun merge, déploiement ou changement applicatif.
