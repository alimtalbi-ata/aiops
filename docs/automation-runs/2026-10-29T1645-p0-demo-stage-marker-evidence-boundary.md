# 2026-10-29 ~16:45 CET — 5/5, correction P0 de sémantique des marqueurs DEMO

**READY_FOR_STABLE=BLOCKED / NO-GO.** Cette livraison reste dans l'unique PR d'intégration [#185](https://github.com/alimtalbi-ata/aiops/pull/185), basée sur la branche #153. Aucune nouvelle PR, aucun merge, aucun push stable, aucun accès Debian, aucune remédiation LIVE.

## Inventaire vérifié avant modification

- `main=27deb9b1a66faf27df8d69b137a63451f7649d80`, `deploy/aiops2-stable=e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (branche protégée). Candidate précédente #185 `ad69a8527fe097cf9f189ad8acf859ff8c13dc50`, 63 commits ahead / 0 behind de stable ; ce n'est PAS une attestation de transport. Base #153 `e5c6b030c374e47f64678f425df78cd147335eec`.
- SHAs sources figés et déjà réutilisés dans #185 : #170 Twin `bec96d26b288394a8c4d878417090e09c8c52a25`, #171 NOC/Evidence `a46b5d0972a10b78ac1a490257bf543592ba3c2b`, #176 Policy `b56488d9ff80c8166c9dd9cf64f24d0b7e3d48c8`, #156 recette `395707e4f4dbc0e15ce6fe44d64776b6f4375aeb`. #177 UI `a539b293d5bc01d6cd71ff6dc5b53b382baa793c` exclue car CI rouge.
- CI de la **candidate précédente** `ad69a852` : quality.yml [40876179461](https://github.com/alimtalbi-ata/aiops/actions/runs/40876179461) SUCCESS (6/6 jobs) et trois workflows hérités SUCCESS. Ces résultats ne qualifient PAS les nouveaux commits.
- Issue transverse [#186](https://github.com/alimtalbi-ata/aiops/issues/186) relue : pipelines OTLP→Loki/Tempo synthétiques rapportés par l'opérateur, sans E2E métier ACME ni approbation GLPI. L'observation terrain antérieure concerne uniquement l'image `e94fe784`, pas la candidate actuelle.

## Lacune P0 prouvée et modification minimale REUSE-FIRST

Le [constat Policy/HITL 4/5](https://github.com/alimtalbi-ata/aiops/pull/185) relève que `app/worker/main.py:execute_stage` enregistre `record_type=stage_marker` avec le claim `POLICY completed` **avant** la réponse Policy ; HITL/REMEDIATE/VERIFY peuvent enregistrer `STAGE_COMPLETED/PASS` sans approbation GLPI, exécution ou vérification indépendante. Ce sont des jalons synthétiques, pas des preuves de succès.

Sans remplacer le Worker V2.2 ni ajouter de service, `app/portal/demo_v2.py:render_demo_v2` affiche désormais, **uniquement lorsqu'un Run DEMO/REPLAY/STORY contient ces étapes STAGE_COMPLETED**, un avertissement explicite : marqueurs synthétiques ≠ décision Policy PASS/SIMULATE, approbation humaine, remédiation, vérification ou LIVE. Les événements Core restent affichés sans altération. `tests/test_demo_v2.py` ajoute deux cas de contrat (présence de l'avertissement pour POLICY/HITL/REMEDIATE/VERIFY ; absence pour NORMALIZE). Commits code `6ae3decb111320905fc9270d92ed45e9c314a5ee`, tests `92bf2d315688dd7a836f0bd98ee87eee6bb9695b` et ajustement de l'assertion `fcd2bc04ec800dde43a9f6a053aa93031a869bca`.

**Ce correctif de présentation ne supprime PAS le défaut d'ordre d'écriture du Worker et ne prouve aucune décision IA.** Le Worker n'est pas transporté par le déployeur quatre images #185 ; ne pas le modifier en cachette ni annoncer l'E2E.

## Matrice anti-duplication et propriétaires

| Besoin | Existant (chemin:symbole, source) | Lacune / adaptation | Contrat / propriétaire | Transport / rollback |
|---|---|---|---|---|
| Twin SAN→Payments | `app/twin/main.py:impact`, #170 `bec96d2` | Topologie sourcée, impact runtime UNKNOWN ; NO_CHANGE | PostgreSQL/HTTP et RBAC, 1/5 Twin | Image Twin prévue, rollback terrain NOT_TESTED |
| Core Run/Incident/Evidence | `app/core/main.py:get_run`, `app/core/demo_evidence_read.py:evidence_refs`, #171 `a46b5d0` | Join incident_id/run_id/evidence_ids terrain UNKNOWN | Reçus Core↔Portal existants, 3/5 NOC | Image Core prévue, rollback NOT_TESTED |
| Policy SIMULATE | `app/policy/main.py:check`, #176 `b56488d` | Worker marque `POLICY completed` avant gate ; ne pas prendre pour PASS | Critique validée, redondance, 4/5 Policy | Image Policy prévue ; Worker NON transporté |
| Portal Demo Studio | `app/portal/demo_v2.py:render_demo_v2`, #185 | Avertissement stage markers sans second read-model | 2 tests ciblés ajoutés, 2/5 UI + 5/5 intégration | Image Portal prévue, rollback NOT_TESTED |
| Release/recette | `deploy/poll-approved-deploy.sh`, `deploy/deploy-acme-p0.py:preflight_host,apply`, #153/#185 ; `scripts/check_demo_release_receipts.py`, #156 | Poller installé portal-only ; propriété Compose, rollback et smoke sur SHA actuel non attestés | 5/5 seul owner stable | **BLOCKED** |

Ordres aux propriétaires : 1/5 préserver le Twin sourcé, aucun nouveau graphe ; 2/5 ne pas fusionner #177 rouge et conserver les disclaimers ; 3/5 conserver le même `run_id` et les refs synthetic sans attestation d'origine ; 4/5 ne proposer un patch Worker qu'avec test HTTP de Policy refusée, sans fausse approbation ni extension de transport non qualifiée. Aucun nouveau workflow CI ni nouvelle PR.

## Qualification

- Tests **ajoutés**, mais **pas exécutés localement** (NOT_TESTED). Checks sur SHA final de cette mise à jour : **PENDING/à reconsulter** ; ne pas réutiliser la CI verte de `ad69a852` pour déclarer cette révision verte.
- Debian : `applied.sha` actuel, déploiement de cette candidate, smoke Core/Twin/Copilot/Portal, auth/RBAC tenant A/B, SAN→Payments runtime, Temporal/Analyst/Critic, Policy→Evidence, rollback réel : **NOT_TESTED**.
- Contrats API : **inchangés**. Contrat de présentation : un `STAGE_COMPLETED/PASS` DEMO n'est jamais une attestation indépendante. Aucun LIVE.
- **Blocage principal unique** : chemin de promotion/déploiement multi-services non qualifié (cron installé portal-only, propriété Compose et restauration terrain inconnues). Action suivante : obtenir le reçu opérateur `deploy/deploy-acme-p0.py --inspect-host` en lecture seule sur checkout propre et SHA exact ; si refus, conserver NO-GO, sans `--apply`. Ensuite seulement revoir une migration du poller et la recette read-only.

## Qualification observée après livraison du code

- SHA **code + tests + step quality.yml** `4b892cdb404a1b7bacbbf86f84f761eb22d7bccb` : [quality.yml run 40905147106](https://github.com/alimtalbi-ata/aiops/actions/runs/40905147106) **completed/success, 6/6 jobs** (`quality-build-package`, `database-migrations`, `mariadb-dr-rehearsal`, `migration-runner-upgrade`, `runtime-e2e`, `release-kit`). Dans le log du job `quality-build-package`, **6/6 tests `test_demo_v2.py` PASS**, dont les deux nouveaux tests de marqueurs synthétiques ; `Ran 6 tests ... OK`. `runtime-e2e` est un test CI synthétique, pas une attestation Debian.
- Autres workflows sur ce **même SHA** : [V2.8 40905146979](https://github.com/alimtalbi-ata/aiops/actions/runs/40905146979), [Offline 40905146981](https://github.com/alimtalbi-ata/aiops/actions/runs/40905146981), [Historical 40905147112](https://github.com/alimtalbi-ata/aiops/actions/runs/40905147112) **completed/success** ; GitHub Check Runs **10/10 SUCCESS**. Ces checks ne qualifient pas une éventuelle révision documentaire ultérieure.
- Les tests locaux, l'authentification/tenant terrain, l'E2E Temporal/Policy/Evidence/Payments et la restauration Docker sur SRV-DEB-05 restent **NOT_TESTED**. La candidate n'est pas déployée ni promue ; **READY_FOR_STABLE=BLOCKED**.
