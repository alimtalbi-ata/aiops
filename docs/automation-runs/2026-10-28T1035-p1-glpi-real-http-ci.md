# 2026-10-28 10:35–10:49 Europe/Paris — P1 GLPI real HTTP negative CI

## Base et lecture préalable
- `main` HEAD initial et revérifié avant écriture : `4652a8893b4ec2fffae8aa515d4b2087259bf7bf`.
- Base dédiée empilée sur draft PR #69, HEAD vérifié `fec7866cf8979fb646e416a150845acdcb84b455` ; aucune modification de la branche d'autrui.
- PR #36, #37, #39, #41, #43 inspectées, ainsi que #69/#73 et autres PR P1 (#77/#80/#85/#90/#96/#101/#107/#112). Continuité, architecture, protocole de qualification, fixture et `quality.yml` lus.
- PR #36 : reprise ciblée des fixtures et contrats ACME déjà portés en amont, sans fusion massive. Ce micro-lot qualifie le lecteur de #69 contre un service réel.

## Fichiers et commits
- `tests/test_glpi_real_http.py` — test HTTP négatif réel, sans transport mock : commit `eb7522a9e8ae67f00305247f86e27a76c1a1e95a`.
- `.github/workflows/quality.yml` — ajout d'un job GLPI/MariaDB réels au workflow existant : commit `30d8d7e5f008ba442563c4fab32d9ef7359fa2d7`.
- `docs/architecture/GLPI-REAL-HTTP-CI-20261028.md` — contrat de preuve, limites et rollback : commit `53044f2564d376d63d2365485d7fa9bfd64061f5`.
- Correctifs CI/test : `20373cd8cd788ad8d6eff834d8390862772d0390` (diagnostic HTTP borné), `6e15566eb722d8d37d45d6de44289697e08eeb33` (page HTML GLPI réelle >64 KiB), `6dc9ce5e632a1d45817420ba90e045b7176052a5` (activation REST API uniquement dans GLPI CI).
- Ce journal et la mise à jour du document de qualification : commit final à consulter dans la PR.
- PR draft : https://github.com/alimtalbi-ata/aiops/pull/120 (base #69).

## Exécution / preuves
- Lecture source GitHub : DONE.
- Tests unitaires GLPI préexistants #69 : exécutés dans `policy-and-static` sur la PR ; **SUCCESS** (pas exécutés localement).
- GitHub Actions [40667157033](https://github.com/alimtalbi-ata/aiops/actions/runs/40667157033), code HEAD `6dc9ce5e632a1d45817420ba90e045b7176052a5` : **completed/success** ; 4 tests HTTP contre GLPI 11.0.9/MariaDB 11.4 réels, dont rejet API d'un jeton CI invalide, refus adaptateur et LIVE. Compilation, tests contractuels, audit statique et Compose : **SUCCESS** dans le workflow de cette branche.
- Échecs précédents **conservés** : [40665784889](https://github.com/alimtalbi-ata/aiops/actions/runs/40665784889) et [40665818736](https://github.com/alimtalbi-ata/aiops/actions/runs/40665818736) (HTML GLPI volumineux), [40666629463](https://github.com/alimtalbi-ata/aiops/actions/runs/40666629463) (diagnostic), [40666980666](https://github.com/alimtalbi-ata/aiops/actions/runs/40666980666) (API réelle désactivée). Corrigés par lecture des logs et activation API **uniquement** sur le conteneur éphémère.
- La branche étant empilée sur #69, le workflow n'inclut pas automatiquement toutes les nouvelles étapes ajoutées à `main` depuis la base : réconciliation requise avant merge.
- La validation du commit documentaire final sera consultée séparément ; ne pas extrapoler le résultat du code HEAD.
- Tests Core/Temporal/GLPI positif, authentification GLPI réelle, ticket créé, corrélation IDs et RBAC serveur : **NOT_TESTED**.
- Aucun endpoint NVIDIA NGX ou Debian contacté ; aucune commande LIVE ni déploiement.

## Risques / blocages
- GLPI 11.0.9 désactive l'API REST par défaut ; le job l'active uniquement dans le conteneur CI jetable via CLI officielle. Si cette activation échoue, le job échoue sans mock.
- Base #69 ancienne par rapport à `main` ; réconciliation des changements `quality.yml` et revue des protections GitHub nécessaires avant fusion.
- Un rejet de jeton CI invalide est une preuve négative limitée, pas une preuve de ticket authentifié ni d'intégration end-to-end.
- Aucun merge tant que checks, conflits et sécurité non vérifiés.

## Prochain micro-lot
1. Réconcilier le workflow de la branche empilée avec `main`, puis revalider tous les checks de sécurité sur la branche fusionnable.
2. Configurer une authentification API GLPI éphémère et un ticket de test réellement créé dans CI, avec vérification d'entité ; jamais de ticket réel revendiqué sans réponse GLPI authentifiée.
3. Raccorder ensuite les scopes Incident/Run/entité à une identité RBAC serveur, avec non-régression DEMO/LIVE et séparation des preuves.
