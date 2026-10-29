# P0 Policy/HITL/Temporal — liaison canonique Worker→Core (29/10/2026, 08:38 Paris)

## État lu avant modification
- GitHub refs vérifiées : `main=27deb9b1a66faf27df8d69b137a63451f7649d80`, `deploy/aiops2-stable=e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Ces refs n'ont pas été modifiées.
- PR existante [#176](https://github.com/alimtalbi-ata/aiops/pull/176), branche `fix/p0-policy-synthetic-critic-fence-20261029-0235`, HEAD initial `766c4cff8bd83566de5e91b2111bf21ca1c07e5e` : draft, mergeable, 3/3 jobs `quality.yml` PR SUCCESS sur le SHA initial ([run 40830520709](https://github.com/alimtalbi-ata/aiops/actions/runs/40830520709)). Pas de nouvelle PR.
- Autres créneaux consultés : Recette [#156](https://github.com/alimtalbi-ata/aiops/pull/156) (Evidence offline #181 intégrée à sa branche, mais release BLOCKED), déployeur #153, Twin #170, NOC #171 (nouvelle qualification HTTP synthétique), UI #169/#177 (CI rouge). Journaux `2026-10-29T0735-p0-core-gate-receipt-fence.md` et autres journaux #156/#171 consultés.
- PR historiques : #140 CI FAILURE, #141 MERGED et CI SUCCESS, #142 CI SUCCESS mais PR non fusionnée, #143 CI SUCCESS, #144 CLOSED non fusionnée (CI historique SUCCESS), #145 CI FAILURE, #146 aucun run PR retrouvé au SHA examiné. Ne pas transposer leurs checks au candidat.
- Convergence #144→#147→#155→#163 déjà présente dans main selon l'historique ; pas de cherry-pick dupliqué.

## Livraison verticale P0 unique
**Défaut** : l'API Worker `POST /api/execution/start` acceptait un `mode=DEMO` fourni par le client sans vérifier le `mode`, `run_id`, `scenario_id`, `status` ni la version du Run canonique Core. Le même Run pouvait donc être démarré sous une identité DEMO demandée mais différente de son mode Core (notamment LIVE). Une validation Policy SIMULATE ultérieure n'aurait pas prouvé cette identité.

**Correction** :
- `app/shared/simulation_policy_contract.py` : `validate_canonical_run_binding` compare strictement `run_id/mode/scenario_id/version/status` au `GET /api/runs/{rid}` canonique. En préflight HTTP : statut CREATED et version exacte ; en activité START : CREATED ou RUNNING (retries idempotents) avec version au moins attendue. Types booléens pour la version refusés.
- `app/worker/main.py` : authentification interne existante maintenue, Run ID limité au segment ASCII `RUN-...` avant construction d'URL, GET Core interne puis validation **avant** connexion Temporal ; HTTP 422 entrée invalide, 409 mismatch, 503 Core indisponible, sans divulgation du contenu Core. `start_run` revalide à l'exécution avant commande START Core. L'écriture START reste protégée par expected_version/idempotency_key Core.
- `tests/test_simulation_policy_contract.py` : quatre nouveaux tests unitaires/AST (cas valide, mismatch LIVE/cross-Run/cross-scenario/version, états terminaux, retries et ordre des garde-fous). Aucun accès réel à Temporal dans ces tests.
- Commits de code/tests successifs : `55f34050f6df405dc03bc2ebe04b0f651ac3f925`, `bea3aea7bb4512315725d8699a31bc70ae81eb6c`, `1ea08ef61dec80e8e3c64b2607dc4660dbb16b38`, `9b3caff60c65bb55c8c2b6eda92a423cfb8d9d26`, `170c6293e36348351f43dfe83e873c36169e4add`.

## Contrats, preuves et limites
- Contrat API Core inchangé ; contrat **interne Worker /api/execution/start restrictif** : requiert un Run Core préexistant CREATED avec version et identité correspondantes. Les démarrages ambigus, les retries HTTP sur un Run déjà RUNNING et les identifiants malformés sont refusés. L'activité START garde sa tolérance aux retries idempotents. Aucune autorisation LIVE ajoutée.
- Ce contrôle n'est **ni atomique** avec START, ni une liaison cryptographique Policy→Run/Evidence, ni une preuve RBAC tenant A/B. Le GET Core utilise le jeton interne, mais l'API de lecture Core actuelle n'est pas une attestation tenant.
- Policy `PASS/SIMULATE` est fondé sur assertions synthétiques fournies par l'appelant ; `RESOLVED` n'atteste aucune remédiation LIVE. Historique Debian communiqué, **non revérifié** : 7 Runs DEMO, 5 BLOCKED sans gate explicative (cause non prouvée), 1 RESOLVED/PASS/SIMULATE, 1 RUNNING ancien (pas de terminaison Temporal attestée).
- Tests de ce lot : `quality.yml` **PENDING** à la rédaction ; ne pas reprendre les PASS de l'ancien HEAD. **NOT_TESTED** : exécution réelle Temporal, HITL authentifié, provenance Evidence, tenant A/B, impact SAN→Payments, E2E Studio, serveur Debian, rollback, `applied.sha`, smoke-tests post-déploiement. Aucune exécution locale ou sur serveur attestée.
- Aucun nouveau workflow CI, aucune modification du poller ou du déployeur. Le déployeur V2 ne transporte pas automatiquement Worker/Policy/Core/Twin.

## Remise Recette 5/5
- **READY_FOR_STABLE=BLOCKED ; NO-GO E2E.** Aucun push `deploy/aiops2-stable`, aucune fusion, aucun SSH/Debian, aucune mutation LIVE.
- Recette [#156](https://github.com/alimtalbi-ata/aiops/pull/156) est seule responsable de l'assemblage et de la promotion, après CI finale verte, paquet multi-services complet, compatibilité, rollback, smoke-tests authentifiés en lecture seule, et `applied.sha` terrain horodaté.
- Prochain lot : tests d'intégration HTTP réels de `POST /api/execution/start` contre Core/PostgreSQL + faux client Temporal instrumenté (sans mutation), puis Temporal sandbox réel et liaison authentifiée Policy/Run/Evidence ; ne pas déclarer E2E sur la seule base de fixtures.

## Complément de recette HTTP réelle
- Commit test HTTP `4fe4118d78d789dadbe7b161d67d9a78f48540c8` : `tests/test_core_demo_policy_real_integration.py` ajoute un Run CREATED synthétique dans PostgreSQL 16 éphémère, lit le véritable Core HTTP, vérifie la liaison valide et refuse un Run LIVE, un RUNNING non éligible et un scénario incohérent. Nettoyage SQL existant préservé. **Aucune exécution Temporal**, aucun effet LIVE.
- Les runs CI intermédiaires `40836931009` et `40837039650` ont leurs trois jobs SUCCESS sur des SHA précédents ; ils ne qualifient **pas** ce nouveau test ni le HEAD documentaire final.
- CI du HEAD final : **à vérifier séparément**, ne pas promouvoir sur la base des jobs intermédiaires. Contrats API publics inchangés.
