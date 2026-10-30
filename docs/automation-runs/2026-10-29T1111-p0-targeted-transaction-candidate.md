# 2026-10-29 11:11 CET — Release P0 5/5 : transport ciblé candidat intégré #185

**READY_FOR_STABLE=BLOCKED / NO-GO**. Un seul candidat de release : [#185](https://github.com/alimtalbi-ata/aiops/pull/185), branche `release/p0-acme-integrated-candidate-20261029-1100`, basée sur #153. Aucun push/merge stable, aucun SSH Debian, aucun LIVE, aucune mutation de données. Deadline initiale 05h dépassée ; nouvelle fenêtre T+6h demandée, T0 précis non attesté.

## Inventaire GitHub vérifié

- `main` : `27deb9b1a66faf27df8d69b137a63451f7649d80` (non protégé au relevé). Stable protégée `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, checks requis `quality-build-package`, `database-migrations`, `mariadb-dr-rehearsal`, `migration-runner-upgrade`, `runtime-e2e`. `main` diverge : ne pas merger en bloc.
- #153 déployeur `e5c6b030c374e47f64678f425df78cd147335eec` ; #156 recette `395707e4f4dbc0e15ce6fe44d64776b6f4375aeb` ; #170 Twin `bec96d26b288394a8c4d878417090e09c8c52a25` ; #171 NOC `a46b5d0972a10b78ac1a490257bf543592ba3c2b` ; #176 Policy `b56488d9ff80c8166c9dd9cf64f24d0b7e3d48c8` ; #177 UI `a539b293d5bc01d6cd71ff6dc5b53b382baa793c` CI rouge, **exclue**.
- #185 ancien HEAD `71e2262942f27406e905d78c23e629994ce02195` : [quality.yml #40854816750](https://github.com/alimtalbi-ata/aiops/actions/runs/40854816750) SUCCESS 6/6 jobs, workflows hérités SUCCESS. Ce résultat ne s'applique **pas** aux nouveaux commits de transport. Les SHAs et checks finaux doivent être lus sur GitHub.
- Source Debian historique : portail V2 accessible au relevé antérieur, **pas de preuve fraîche**. `applied.sha`, ownership Docker, logs et recette terrain : **NOT_TESTED**.

## Matrice anti-duplication et contrat de déploiement

| Besoin métier | Code existant réutilisé (SHA #185 initial) | Lacune prouvée / adaptation P0 | Copie / rebuild / restart / rollback | Propriétaire |
|---|---|---|---|---|
| Core run/events/gates | `app/core/main.py` + `app/core/demo_evidence_read.py:register_demo_evidence_routes` | Nouveau module non transporté par #153 | **Image Core ciblée**, redémarrage Core seul, image antérieure réservée | 5/5 + 3/5 contrat |
| Temporal Worker | `app/worker/main.py` (base V2.2) | Pas de portage Worker #176 ; exécution E2E UNKNOWN | **Aucun changement**, aucun restart Worker | 4/5 |
| Twin SAN→Payments | `app/twin/main.py:impact` (#170) | Impact topologique inverse sourcé, panne runtime UNKNOWN | **Image Twin ciblée**, restart Twin, image antérieure réservée | 1/5 |
| Policy SIMULATE/HITL | `app/policy/main.py` (#176 adapté) | Garde critic/redondance/confiance non transportée | **Image Policy ciblée**, restart Policy, image antérieure réservée | 4/5 |
| Evidence / NOC | `app/core/demo_evidence_read.py`, `app/portal/demo_ledger_read.py:read_demo_ledger` (#171) | Références synthétiques, non attestées ; identité tenant UNKNOWN | Core + Portal seulement, **aucun second ledger** | 3/5 |
| Demo Studio V2 | `app/portal/demo_v2.py`, `app/portal/main.py` | Injection d'ancre #153 ne transporte pas route AI Ledger | **Image Portal complète ciblée**, restart Portal, image antérieure réservée | 2/5 |
| Recette | `scripts/check_demo_field_readonly.py`, `check_demo_evidence_receipts.py`, `check_demo_release_receipts.py` (#156) | Réception terrain manquante | Scripts **depuis checkout approuvé**, sans nouvelle CI | 5/5 |
| Déployeur | `deploy/deploy-demo-studio-v2.sh` + `poll-approved-deploy.sh` (#153) | **P0 principal** : ne transporte que portail V2 | Nouveau `deploy/deploy-acme-p0.py` pour transaction **opérateur uniquement** ; poller non raccordé | 5/5 |

Le nouveau script **ne copie aucun fichier** dans le répertoire Debian existant : `docker build` construit Core/Twin/Policy/Portal depuis le checkout Git approuvé ; `docker compose -p aiops2-rebuild --no-deps --no-build --force-recreate` cible uniquement ces quatre services, avec override d'images. Avant toute mutation, il exige Docker rootless/socket connus, fichiers Compose et .env existants non exposés, secret viewer distinct, conteneurs sains **déjà propriétaires Compose du même projet, même répertoire/config**. Les images précédentes sont conservées sous tags rollback, un override rollback est conservé ; en cas d'échec après switch, recréation ciblée avec anciennes images, et marqueur `DEPLOYMENT_BLOCKED` si rollback échoue. **Ni DB, ni Temporal, ni Copilot, ni volume, ni conteneur tiers** n'est volontairement touché. Aucun `docker compose down`, aucune migration ni source overwrite.

Le script est **read-only par défaut** et renvoie `MANUAL_APPROVAL_REQUIRED / NO_GO` si la matrice de chemins est couverte ; les chemins non reconnus sont `BLOCKED`. L'application exige **ensemble** `--apply --operator-approved` et `AIOPS_RELEASE_APPLY=YES`. Même si l'application réussissait, le résultat serait `APPLIED_UNATTESTED / NO_GO`, sans écriture `applied.sha` ni prétention E2E. La réussite du rollback n'est pas attestée tant qu'un essai terrain contrôlé n'est pas observé.

**Limite P0 bloquante** : le poller **actuellement installé** sur SRV-DEB-05 n'appelle pas ce script, refuse les changements `app/core`, `app/twin`, `app/policy`, `app/portal/main.py`, `.github/*`, `deploy/*` et n'est pas mis à jour par les PR. Le script ciblé ne rend donc pas le cron automatiquement compatible. La présence du conteneur Portal `aiops2-rebuild-portal` ne prouve pas sa propriété Compose ; si créé manuellement, préflight refuse avant mutation. L'intégration du poller, la compatibilité Compose terrain et le rollback réel nécessitent une revue opérateur indépendante avant promotion.

## Recette opérateur proposée, **NON exécutée**

Depuis un checkout local **propre** au SHA candidat approuvé (et après vérification de sa CI/protection), plan sans mutation :

```bash
SHA="$(git rev-parse HEAD)"
python3 deploy/deploy-acme-p0.py --stable-sha e54c4e9a9b37e6229559a1b587c9a06b4741a8b3 --candidate-sha "$SHA"
```

L'option `--apply` **ne doit pas être exécutée** tant que les préconditions de propriété Docker, sauvegarde, rollback, source Compose, jeton viewer et autorisation opérateur ne sont pas revues. Après déploiement approuvé : exécuter **séparément** `scripts/check_demo_field_readonly.py` avec quatre forwards loopback Core/Twin/Copilot/Portal, vérifier `applied.sha` via `--expected-sha`/`--applied-sha-file`, collecter logs du poller, `docker inspect` limité aux quatre conteneurs et receipts Core/Portal (sans jeton ni payload sensible), puis `check_demo_evidence_receipts.py` et `check_demo_release_receipts.py`. Archivage UTC et SHA requis. Le poller seul ne qualifie pas l'E2E.

## Missions transverses publiées

Commentaires de coordination sur PR #170 (Twin), #177 (UI), #171 (NOC), #176 (Policy), #185 (release) : réutiliser #185, **aucune micro-PR**, signaler uniquement un défaut P0 avec test ou NO_CHANGE. UI rouge exclue ; Worker non écrasé ; aucune nouvelle fonctionnalité, service ou workflow.

## Tests et décision

- Nouveaux fichiers : `deploy/deploy-acme-p0.py`, `tests/test_deploy_acme_p0.py`, exécution ajoutée à **quality.yml existant**. Tests offline : chemins couverts/non couverts, Git clean/ascendance, socket rootless, absence d'approbation, rollback simulé et marqueur d'échec. **Docker réel NOT_TESTED**.
- À la création du journal : nouvelle CI candidate **PENDING**, ne pas attribuer le succès de `71e2262` au HEAD modifié. Aucun test sur SRV-DEB-05 ni attestation indépendante.
- Contrats E2E `run_id`/`incident_id`/`evidence_ids`, tenant RBAC, Temporal exécuté, Policy réelle, impact Payments observé, `applied.sha`, rollback Docker : **NOT_TESTED**. Les reçus synthétiques sont des références, non une validation indépendante.
- **Blocage unique : chemin de déploiement Debian non qualifié de bout en bout (ancien poller + ownership Compose + rollback terrain).** Prochain acte : CI exacte du HEAD, revue du contrat du nouveau script et de la migration manuelle du poller ; sinon réduire la démo aux seules capacités déjà réellement attestées, avec étapes UNKNOWN. **Aucune promotion stable**.
