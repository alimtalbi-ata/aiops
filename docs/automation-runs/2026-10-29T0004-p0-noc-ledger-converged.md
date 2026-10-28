# 2026-10-29 00:04–00:07 Europe/Paris — RELEASE P0 NOC/Copilot — convergence Ledger

## Lecture et baseline avant écriture
- `main` HEAD consulté : `13c455256f34e5e0f0ac55146326888b0fb84c42` (ne pas confondre avec branche V2).
- Demo Studio V2 HEAD consulté : `296ab8136efe9a9068cd6b6045236c5abc52694b`. La pile NOC #167 HEAD : `2cac214736b2a6a8eca70581537413003096baee`. Vérification refs avant modification.
- PR ouvertes, #140–#146, #145/#149/#154/#161/#162/#167, Recette #156, Twin #168 et journaux NOC/Policy consultés ; `docs/PROJECT-CONTINUITY.md` lu. #141 fusionnée, #144 fermée non fusionnée. Ne pas recopier les contrats contradictoires de Twin/Story.
- Comparaison GitHub : #167 et V2 avaient divergé depuis `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; V2 avait 7 commits propres (Policy, tests, workflow). **Aucun merge de la pile #167 vers V2** : portage ciblé des 19 fichiers NOC/CI/docs dans un commit créé sur HEAD V2, conservant les 7 commits V2.

## Livraison verticale et commits
- Branche dédiée : `release/p0-noc-ledger-converged-20261029-0004`, base V2 SHA `296ab8136efe9a9068cd6b6045236c5abc52694b`.
- Commit de code/tests/contrats : `360ba5713f22dc89e93f4a90919b41dce00c04e2`. 19 fichiers : `app/core/demo_evidence_read.py`, `app/core/main.py`, `app/portal/demo_ledger_read.py`, `app/portal/main.py`, `app/shared/tenant_scope.py`, `compose.yml`, `config/.env.example`, `deploy/init-env.sh`, `.github/workflows/quality.yml`, `tests/test_demo_ledger_read.py`, `tests/test_demo_ledger_real_http.py`, deux contrats `docs/demo/*LEDGER-EVIDENCE-REFS-V1.md` et six journaux historiques NOC.
- Workflow fusionné **sans écraser** l'isolation `AIOPS_POLICY_STATE_DB` du job Policy et du release-kit de V2. Une seule CI existante `quality.yml`, pas de workflow créé ni de lancement manuel.
- PR candidate unique **draft** : [#171](https://github.com/alimtalbi-ata/aiops/pull/171), base `feat/demo-studio-v2-delivery-20261028`. Les six PR NOC historiques restent des sources, pas six candidates indépendantes. Aucun push sur `deploy/aiops2-stable`.
- Journal de ce passage : le présent fichier, commit documentaire distinct à lire dans l'historique de #171. Les checks du SHA final sont à qualifier séparément.

## Contrats et sécurité
- `GET /api/demo-studio/runs/{rid}/ai-ledger` : viewer Bearer `AIOPS_PORTAL_READ_TOKEN` distinct, vérifié avant I/O ; jeton interne Core jamais transmis au navigateur ; lecture seule, réponse bornée `aiops.demo-ledger-read.v1`. Auth viewer invalide -> HTTP 401 ; source/Core 401/LIVE/tenant/absence/contradiction -> 503 `UNKNOWN` no-store.
- `GET /api/noc/runs/{rid}/evidence-refs` : Bearer interne Core avant SQL, Evidence et événement Run persistés, IDs Analysis/Critique concordants, empreinte SHA-256 et `known_at` timezone-aware non futur au-delà de 5 min. Contrat `aiops.core-demo-evidence-refs.v1`, classification `SYNTHETIC_ONLY`, `tenant_acl_qualified=false`, `runtime_attested=false`. 401 sans jeton, 503 pour données non qualifiées.
- Refus des citations sans Evidence, dupliquées, cross-Run, hors scope tenant, d'horodatages futurs, de LIVE et de source manquante. Tests unitaires négatifs et HTTP réel avec Core/Portal/PostgreSQL 16 sont inclus.
- La cohérence interne des références ne prouve pas le contenu d'origine, les métriques observées, une ACL tenant A/B authentifiée, un diagnostic Ollama ni l'impact Payments.

## CI, recette et risques
- **Tests exécutés dans ce passage sur le nouveau SHA** : en attente de GitHub Actions au moment du premier journal ; aucun PASS revendiqué.
- **Résultats historiques, non transférables au nouveau SHA** : sur #167 `2cac2147`, [quality #40780596520](https://github.com/alimtalbi-ata/aiops/actions/runs/40780596520) completed/failure (database-migrations SUCCESS, quality-build-package FAIL Policy, runtime-e2e FAIL, release-kit SKIPPED) et [V2.8 #40780596545](https://github.com/alimtalbi-ata/aiops/actions/runs/40780596545) FAIL. Sur V2 base `296ab813`, [quality #40760105225](https://github.com/alimtalbi-ata/aiops/actions/runs/40760105225) SUCCESS ; ne pas en déduire que la combinaison passe.
- **NOT_TESTED** : tests locaux, isolement tenant A/B authentifié, CI Ollama 4B avec provenance `CI_SIMULATED_LLM` (runtime E2E hérité utilise un provider déterministe et n'est pas une qualification LLM), SAN CRC/Payments p95 observés, causalité Twin, E2E Policy SIMULATE/Evidence, captures et vidéo, Debian/cron, `applied.sha`, rollback.
- **Déploiement : BLOCKED.** Le script V2 ne copie que `demo_v2.py` et `test_demo_v2.py` et injecte `portal/main.py` ; il ne déploie ni `app/core/demo_evidence_read.py` ni les autres modules NOC/Portal. Promotion partielle = 503 volontaire, pas GO.
- **READY_FOR_STABLE=BLOCKED / NO-GO** tant que CI globale de #171 non verte, compatibilité UI/Policy/Temporal non prouvée, couverture Core/Portal, rollback et smoke-test en lecture seule non qualifiés. Aucun accès Debian, aucune remédiation LIVE, aucun appel NGX, aucun secret prod.
- Transfert vers [Recette 5/5 #156](https://github.com/alimtalbi-ata/aiops/pull/156) : candidate #171 uniquement, pas de push stable par owner NOC. Le schedule 5 seul décide une promotion après recette et attestation indépendante.

## Prochain micro-lot
Lire les jobs et logs de `quality.yml` et V2.8 sur le **SHA final** #171, corriger uniquement les régressions de convergence dans le même périmètre, ne pas affaiblir Policy/RBAC ; puis transmettre les résultats exacts à #156. Si CI rouge : NO-GO documenté, aucun déploiement.
