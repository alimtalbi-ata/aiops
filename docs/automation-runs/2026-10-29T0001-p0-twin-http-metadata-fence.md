# 2026-10-29 00:01 CET — ACME Twin : en-têtes HTTP fail-closed

## Sources et concurrence
- HEAD `main` avant travail et avant journal : `13c455256f34e5e0f0ac55146326888b0fb84c42`.
- `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **non modifiée**.
- Base de travail : PR #165 `f6f8d17c0c4a6a33a6821f49d6380311c41de96b`, empilée sur #159 → #157 → #148 → #142. Les checks historiques #142 [40744150243](https://github.com/alimtalbi-ata/aiops/actions/runs/40744150243) et #148 [40760838278](https://github.com/alimtalbi-ata/aiops/actions/runs/40760838278) sont `completed/success` sur leurs SHAs propres ; #165 [40777607084](https://github.com/alimtalbi-ata/aiops/actions/runs/40777607084) également. `main` diverge de la pile ; aucune fusion massive.
- PR #140/#143/#145/#146 ouvertes, #141 fusionnée, #144 fermée non fusionnée ; #156 Recette est **BLOCKED**, #166/#167 ont une CI globale rouge. Branches et journaux concurrents, `docs/PROJECT-CONTINUITY.md`, `quality.yml`, contrat Twin et seed SQL consultés.
- Branche propre `feat/p0-twin-http-metadata-fence-20261028-2357`, [PR draft #168](https://github.com/alimtalbi-ata/aiops/pull/168) base #165. Pas d'écriture dans les autres branches.

## Micro-livraison et contrat
- Commits code/tests/docs : `8489a24759293e6d2790f48e063f9cd96df5b777` ; borne anti-déni de service sur `Content-Length` : `501c48f6c2efef9d18bee83e53339cc3a43a3970`.
- Fichiers : `scripts/qualify_acme_twin_readonly.py`, `tests/test_twin_impact_real_integration.py`, `docs/demo/ACME-TWIN-READONLY-QUALIFICATION-V1.md`, ce journal.
- Contrat API **inchangé** : `GET /api/twin/impact/{node_id}`. Contrat CLI **inchangé** : `aiops.acme-twin-readonly-qualification.v1`. Validation plus stricte des réponses HTTP 401 et 200 : `Cache-Control: no-store` unique, JSON UTF-8, pas de compression ni framing ambigu, `Content-Length` non dupliqué et borné avant conversion, `WWW-Authenticate: Bearer` unique en 401 et `nosniff` en 200. Réponse malformée → `BLOCKED / NO_GO` avec code fixe, sans fuite de jeton.
- Source du chemin **synthétique** : `db/migrations/005_seed_acme.sql`, arêtes `ACME-E08 → E06 → E04 → E02 → E01`, SAN-A → stockage → VM → application → service → Payments. **Aucune liaison SAN → hôte** dans le seed ; le lien VM → hôte est indépendant. L'atteignabilité ne prouve pas une panne Payments, une causalité runtime ou un basculement SAN-B.

## Tests et preuves réellement observés
- `quality.yml` existant, sans workflow parallèle. Run code initial [40784031604](https://github.com/alimtalbi-ata/aiops/actions/runs/40784031604), SHA `8489a247` : `completed/success`, trois jobs verts. Logs Twin : 10/10 tests OK, nouveau test HTTP metadata inclus, contre **vrai Twin Docker + PostgreSQL 16 éphémère** ; 5/5 tests Core NOC OK. Les mutations d'en-têtes sont des variantes unitaires, pas des serveurs intégrés.
- Run code final [40784175216](https://github.com/alimtalbi-ata/aiops/actions/runs/40784175216), SHA `501c48f6c2efef9d18bee83e53339cc3a43a3970` : **`completed/success`**, trois jobs `policy-and-static`, `core-postgres-noc-real-integration`, `grafana-real-integration` verts. Logs du job Core/Twin consultés : **10/10 tests Twin OK** dont longueur `Content-Length` de 5000 chiffres refusée ; 5/5 Core NOC OK. Grafana conteneur réel, tests sécurité et statiques exécutés.
- Le commit de ce journal est documentaire et son propre SHA/checks doivent être revérifiés séparément ; ne pas transférer automatiquement le statut CI du code.
- Tests locaux, Debian, `applied.sha`, captures et recette client : **NOT_TESTED**.

## Décision et handoff
**READY_FOR_STABLE=BLOCKED / GO E2E=NO-GO.** La qualification des métadonnées HTTP est verte sur seed CI, pas une recette de livraison. La pile Twin diverge de `main`, le déployeur V2 ne transporte pas `app/twin/main.py`, tenant RBAC, CMDB authentifiée, Core → IA → Policy SIMULATE → Evidence → Studio, rollback terrain, smoke-tests Debian et `applied.sha` attesté restent **NOT_TESTED**. La sonde exige volontairement des en-têtes stricts ; un déploiement qui ne les expose pas sera `BLOCKED`, jamais silencieusement accepté.

**Prochain micro-lot** : remettre la pile et les SHAs à la Recette 5/5 (#156), converger les contrats avec `main` sur une branche d'assemblage distincte, qualifier le transport effectif Twin et le rollback, puis seulement exécuter la recette terrain lecture seule avec attestation horodatée opérateur. Les lots 1–4 ne poussent pas sur stable.

Aucun accès Debian, aucun merge, aucun déploiement, aucune migration ni action LIVE.
