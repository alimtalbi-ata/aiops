# 2026-10-29 — P0 ACME Twin, compatibilité lecture interservices

## Sources et coordination
- HEAD main lu : `27deb9b1a66faf27df8d69b137a63451f7649d80`.
- Stable lu : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; aucune modification.
- PR ouvertes et branches feat/* inspectées. Candidate unique [#170](https://github.com/alimtalbi-ata/aiops/pull/170), basée sur main, reprend les corrections sourcées #142 puis #148 ; ces PR historiques ne sont pas fusionnées.
- Autres créneaux : [#156 Recette 5/5](https://github.com/alimtalbi-ata/aiops/pull/156), [#153 déployeur](https://github.com/alimtalbi-ata/aiops/pull/153), [#176 Policy](https://github.com/alimtalbi-ata/aiops/pull/176), UI #169/#177, NOC #171. Journaux `docs/automation-runs` et contrat du 05:04 consultés.
- Diff candidate/main vérifié avant modifications : 12 commits ahead, 0 behind, sans conflit constaté.

## Livraison verticale P0
**Problème** : depuis le durcissement des lectures Twin (anciennement anonymes), Portal `shared.http.get_json` utilise `AIOPS_INTERNAL_TOKEN` alors que Twin n'acceptait que `AIOPS_ADMIN_TOKEN`. Le script `deploy/init-env.sh` les génère identiques initialement, mais rien ne garantit cette égalité dans une installation existante. L'appel Portal→Twin pouvait donc devenir 401/UNKNOWN.

**Correction ciblée** :
1. `app/twin/main.py` accepte sur les routes de lecture Twin les deux identités Bearer configurées, sans modifier l'auth administrateur de `POST /api/twin/synthetic-event`.
2. `compose.yml` passe le secret interservice existant au conteneur Twin ; aucun nouveau secret ni workflow CI.
3. `.github/workflows/quality.yml` passe en CI un jeton interne **différent** du jeton admin au véritable conteneur Twin + PostgreSQL 16 éphémères.
4. `tests/test_twin_impact_real_integration.py` teste les lectures HTTP sous identité interne et le refus HTTP 401 de mutation synthétique, avec contrôle d'absence d'observation DB créée.
5. `docs/demo/ACME-TWIN-IMPACT-DIRECTION-V1.md` documente le contrat et ses limites.

**Contrat** : les lectures internes n'attestent ni tenant RBAC, ni panne runtime, ni causalité Payments. `tenant_acl_qualified=false`, `runtime_impact_state=UNKNOWN`. Les arêtes SQL `ACME-E08/E06/E04/E02/E01` restent la seule provenance du chemin synthétique SAN-A→stockage→VM→OraclePay→service→Payments ; **aucun SAN→hôte inventé**. Le modèle Portal SAN→ESX reste distinct et non joint.

## Validation / preuves
- Commits du lot : `52e62f78cd712ce5299ab4373f05365b275b1ce6` (auth Twin), `046caf022fb20ace138cbbf48299e973a44058c7` (Compose), `ad8959a0a9b59dac07cec345365d3889def2b571` (CI), `a363d90b6e8aba26ad8e57b04253025242a3b73b` (test), `0281c0d2fdee974bddd4d442245953f76973c2a8` (contrat).
- Branche/PR : `feat/p0-acme-twin-main-candidate-20261029-0004`, PR #170 draft ; le SHA final inclura ce journal.
- Tests locaux ciblés : **NOT_TESTED** (environnement GitHub privé non monté et aucune infrastructure Docker/PostgreSQL disponible dans ce créneau).
- Nouvelle CI `quality.yml` sur SHA final : **PENDING / NOT_TESTED** tant que GitHub Actions n'a pas publié un résultat vérifié. Les succès précédents de #170 ne valent pas pour ce lot.
- Test Portal navigateur réel avec jetons distincts : **NOT_TESTED**. Le test nouveau vérifie le service Twin réel et son isolation lecture/écriture, pas un E2E Portal.
- Debian SRV-DEB-05, `applied.sha`, smoke-tests et rollback : **NOT_TESTED**.

## Blocages et prochain lot
- `config/prometheus/prometheus.yml` scrappe toujours Twin `/metrics` **sans Bearer** ; le durcissement Twin entraîne HTTP 401. Ne jamais mettre un jeton admin en clair dans un fichier versionné. Identité scrape de moindre privilège + test réel requis.
- Le déployeur stable actuel ne transporte que Demo Studio V2 et ne couvre pas Twin/Core/Copilot/Policy ; compatibilité release non qualifiée.
- ACL tenant A/B, liaison Core→IA→Policy SIMULATE→Evidence→Studio, rollback et preuves terrain restent **NOT_TESTED**.
- **READY_FOR_STABLE=BLOCKED ; overall=NO_GO**. Remettre au seul schedule 5/5 Recette #156 pour assemblage, vérifications et décision. Aucun push vers `deploy/aiops2-stable`, aucune fusion, aucun accès Debian ni remédiation LIVE.
