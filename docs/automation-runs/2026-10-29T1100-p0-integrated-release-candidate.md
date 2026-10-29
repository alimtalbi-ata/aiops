# 2026-10-29 11:00 CET — Release P0: candidate intégrée minimale (revue, NON déployable)

**READY_FOR_STABLE=BLOCKED / NO-GO.** Aucun merge stable/main, aucun accès Debian, aucune mutation LIVE. Cette branche est basée sur #153 `e5c6b030c374e47f64678f425df78cd147335eec`, lui-même descendant fast-forward de stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. `main` est `27deb9b1a66faf27df8d69b137a63451f7649d80` et diverge de stable : ne jamais merger main en bloc.

## SHAs figés, quality.yml vérifiée **sur les branches sources uniquement**

| Domaine | PR | SHA | CI isolée | Décision d'intégration |
| --- | --- | --- | --- | --- |
| Déployeur/rollback portal | #153 | `e5c6b03` | [SUCCESS](https://github.com/alimtalbi-ata/aiops/actions/runs/40819754378) | Base, transport insuffisant |
| Twin SAN→Payments hypothèse topologique | #170 | `bec96d2` | [SUCCESS](https://github.com/alimtalbi-ata/aiops/actions/runs/40847018907) | Portage ciblé impact inverse et auth, préserve acme-quality |
| NOC/Evidence | #171 | `a46b5d0` | [SUCCESS](https://github.com/alimtalbi-ata/aiops/actions/runs/40849991573) | Routes Core+Portal, projection viewer fail-closed |
| Policy/Worker | #176 | `b56488d` | [SUCCESS](https://github.com/alimtalbi-ata/aiops/actions/runs/40850869523) | Policy durcie sur base V2.2; Worker **non porté** (base Worker V2.2 divergente, régression possible) |
| Recette read-only | #156 | `395707e` | [SUCCESS](https://github.com/alimtalbi-ata/aiops/actions/runs/40852663529) | Scripts offline et tests, sans attestation indépendante |
| UI | #177 | `a539b29` | [FAILURE](https://github.com/alimtalbi-ata/aiops/actions/runs/40847845287) | Exclue, ne pas contourner CI rouge |

Les PR historiques #140–#146 ont été revues lors des précédentes recettes : #141 fusionnée, #144 fermée, #140/#145 rouge, #142/#143 vert isolé, #146 sans check HEAD confirmé. Aucun ancien correctif n'est fusionné en bloc.

## Contrat de ce candidat

- **Twin** : lecture authentifiée de l'impact inverse, `affected` = candidats dépendants de topologie **non observés**, `runtime_impact_state=UNKNOWN`, aucune preuve de panne Payments. L'endpoint qualité ACME existant est conservé.
- **Core→Portal** : références Evidence synthétiques et lecture AI Ledger viewer sous auth, sans exposition du jeton interne, sans qualification ACL tenant ni preuve runtime indépendante. Les champs `run_id`, `evidence_ids` et références Critique/Policy sont soumis aux refus fail-closed existants.
- **Policy** : exigences booléennes strictes pour critic/redundance/fraîcheur ; refus `SIMULATE/PASS` si redondance absente et seuil de confiance insuffisant, sans autoriser LIVE. La chaîne Worker/Temporal **n'est pas intégrée** depuis #176 : son fichier 140 lignes écraserait le Worker V2.2 de 402 lignes.
- **Recette** : scripts `check_demo_stable_coverage.py`, `check_demo_field_readonly.py`, `check_demo_evidence_receipts.py`, `check_demo_release_receipts.py` ; quality.yml existant étendu aux tests de ledger et Evidence. La sortie offline reste `NO_GO` même avec des reçus cohérents.

## Matrice exacte de déploiement (candidate vs déployeur #153)

| Modules | Copie | Rebuild | Restart | Tests | Rollback | État |
| --- | --- | --- | --- | --- | --- | --- |
| `app/portal/demo_v2.py`, `tests/test_demo_v2.py` | Déployeur #153 : oui | Portal image | Portal seul | CI source ; terrain NOT_TESTED | Sources + conteneur Portal prévus, terrain NOT_TESTED | BLOCKED jusqu'à smoke |
| `app/core/main.py`, `app/core/demo_evidence_read.py` | NON | NON | NON | CI candidate PENDING | NON | BLOCKED |
| `app/twin/main.py` | NON | NON | NON | CI candidate PENDING | NON | BLOCKED |
| `app/policy/main.py` | NON | NON | NON | CI candidate PENDING | NON | BLOCKED |
| `app/portal/main.py`, `app/portal/demo_ledger_read.py`, `app/shared/tenant_scope.py` | NON (main.py seulement injection ciblée V2) | NON | NON | CI candidate PENDING | NON | BLOCKED |
| `scripts/check_demo_*.py`, tests et `.github/workflows/quality.yml` | NON | N/A | N/A | CI candidate PENDING | SHA Git précédent | BLOCKED pour recette terrain |
| Worker/Temporal/Copilot | Pas de changement intégré | NON | NON | E2E NOT_TESTED | NON | BLOCKED |

**Blocage unique de promotion : le poller `deploy/poll-approved-deploy.sh` refuse précisément ces chemins, et `deploy/deploy-demo-studio-v2.sh` ne les copie, rebuild, restart ou restaure pas.** Ne pas assouplir la garde avant déployeur transactionnel multi-services, compatibilité, sauvegarde et rollback vérifiés. Une CI verte isolée ou intégrée ne permet pas de contourner ce contrat.

## Qualification et terrain

- Tests exécutés localement dans ce cycle : **NOT_TESTED** (pas de clone source disponible). CI du SHA intégré : **PENDING** à la création ; vérifier `quality.yml` sur le HEAD exact et journaliser son résultat réel. Aucun nouveau workflow.
- **NOT_TESTED** : chaîne Core→Temporal→Analyst/Critic→Policy→Evidence→Portal, lien `incident_id`, impact Payments observé, RBAC tenant A/B, provenance indépendante, rollback Docker multi-service, protections GitHub, `applied.sha` authentifié, smoke SRV-DEB-05. Les références synthétiques ne prouvent pas la vérité de la source.
- Recette post-déploiement read-only (à exécuter seulement après approbation) : requêtes authentifiées Core/Twin/Copilot/Portal sur loopback, exports séparés, `python scripts/check_demo_evidence_receipts.py ...`, puis `python scripts/check_demo_release_receipts.py ...` et archivage horodaté sans secret. Exiger `applied.sha` observé, SHA du code réellement transporté, logs du poller et rollback qualifié. Le poller n'est pas un test E2E.
- Prochain acte **P0 unique** : déployeur multi-services transactionnel qui transporte exactement ces modules avec sauvegarde, rebuild/restart ciblés, vérification read-only et rollback. Sinon réduire le scope à la seule démo Portal et afficher toutes les étapes non prouvées UNKNOWN.
