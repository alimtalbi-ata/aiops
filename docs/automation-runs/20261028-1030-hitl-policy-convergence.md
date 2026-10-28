# P0 HITL — convergence Policy deny-only — 2026-10-28 10:30 Europe/Paris

## Lecture préalable / SHA de départ
- `main` HEAD au départ et avant création de branche: `bb4665ab0eb41b43df43ea893e28ac86ef640863`.
- Revues: PR ouvertes #36/#37/#39/#41/#43, #49, #72, #76, #106 ; continuité, architecture, décisions, stratégie de tests et `.github/workflows/quality.yml`.
- PR #36 `app/policy/execution_fence.py` : réserve des admissions simulation-only, jamais permission LIVE ; dépend de `autonomy_store` absent de main. Réutilisation du principe seulement, sans merge massif.
- La PR #76 était `dirty` / conflictuelle avec `main` après les commits récents. Ne pas fusionner à l'aveugle ; convergence ciblée sur nouvelle branche depuis main.

## Fichiers et commits
- Branche `fix/policy-hitl-deny-main-convergence-20261028-1030`, draft [PR #118](https://github.com/alimtalbi-ata/aiops/pull/118).
- `app/policy/main.py`: [`9a19c52fea118ece5cd757a197ac6f9494226684`](https://github.com/alimtalbi-ata/aiops/commit/9a19c52fea118ece5cd757a197ac6f9494226684), portage ciblé du verrou de PR #76 ; LIVE EXECUTE/RESOLVE/REMEDIATE/CANCEL refusés malgré `human_approved=true`.
- `tests/test_policy_safety.py`: [`96dbd1892653b0d394fcaf1e65acd758f410c40b`](https://github.com/alimtalbi-ata/aiops/commit/96dbd1892653b0d394fcaf1e65acd758f410c40b), 14 tests (11 tests Policy de #76 + 3 nouveaux tests HTTP FastAPI en processus), refus d'un booléen d'approbation forgé, modes/commandes invalides, préservation SIMULATE.
- `docs/DECISION-LOG.md`: `818b487d4ed9c3628b1bb99c092929dfa67693fc`, ADR-0018.
- `docs/PROJECT-CONTINUITY.md`: `3e2f88aa485d3ed2934e2fe077d880bb528602a5`, reprise de contexte.
- Ce journal : commit documentaire à consulter sur la PR ; aucun commit vide, aucun écrasement de branche existante.
- PR #76 a reçu en amont les trois tests HTTP via `e5b7cba894d5b6140703322df97f47b0dd7caaf1` et le journal `fb1a9285d321b6adfdfd237cca7952756a363b0f`. Elle est supersédée fonctionnellement par #118 mais pas supprimée avant vérification.

## Tests réellement exécutés / statut
- Ancien HEAD #76 `840eff93`: [GitHub Actions #40615101519](https://github.com/alimtalbi-ata/aiops/actions/runs/40615101519) `completed/success` sur 11 tests Policy, **ne couvre pas** les trois nouveaux tests HTTP.
- HEAD de #76 après ajout documentaire `fb1a9285`: [GitHub Actions #40664342116](https://github.com/alimtalbi-ata/aiops/actions/runs/40664342116) initialement `queued`, résultat à vérifier.
- Nouveau HEAD #118: `quality.yml` doit exécuter `test_policy_safety.py` et les autres étapes existantes ; **PENDING/NOT_TESTED** tant que les jobs du HEAD final ne sont pas confirmés. Aucun PASS extrapolé.
- HTTP Policy = test de route en processus, **pas** intégration à un service Docker. Core/Temporal/RBAC/Evidence, HITL SQLite sandbox en service, Ollama 4B, NGX 192B, E2E, Debian et LIVE: **NOT_TESTED/BLOCKED**. Aucune simulation silencieuse de service autre que l'endpoint LLM n'a été introduite.

## Risques / rollback / prochain micro-lot
- Le contrat Policy ne porte encore ni identité Core/RBAC ni jeton HITL lié au Run canonique ; ce correctif est un **refus déterministe**, pas un mécanisme d'approbation LIVE.
- Le Worker a déjà un refus LIVE séparé, mais son contrat de mode/Policy reste à converger depuis #72. Pas de garantie E2E à ce stade.
- Ne fusionner #118 que si `main` et HEAD sont revérifiés, absence de conflits et checks de sécurité/CI réellement verts. Ne jamais réactiver `human_approved` comme autorisation autonome lors d'un rollback.
- Prochain micro-lot: fusionner la protection si sûre, fermer #76 comme supersédée après vérification ; puis relier HITL sandbox à Core Run/RBAC authentifiés et Evidence append-only, tests de rejeu/concurrence sur services éphémères.
- Aucun accès au serveur Debian 10.79.94.202 ni au portail privé, aucune commande LIVE, aucun déploiement, aucun secret production, aucune capture LIVE.

## CI confirmée sur le HEAD journal `aafa2e2be1a9a3bb5a6f09edc5c00bfcd487c76d`

- [PR quality #40664498414](https://github.com/alimtalbi-ata/aiops/actions/runs/40664498414) et [push quality #40664492518](https://github.com/alimtalbi-ata/aiops/actions/runs/40664492518) : `completed/success` sur ce SHA exact.
- Jobs vérifiés : `policy-and-static` **success** (14 tests Policy, 3 nouveaux tests HTTP explicitement `ok` dans les logs ; compilation, portail/NOC, préflight secrets, audit statique, Compose config), `grafana-real-integration` **success** (vrai conteneur Grafana éphémère, HTTP health et test adaptateur). Cela **ne teste pas** Core/Temporal/RBAC/Evidence ni Ollama/NGX.
- Échec intermédiaire non masqué : [push #40664393548](https://github.com/alimtalbi-ata/aiops/actions/runs/40664393548) sur le commit Policy seul `9a19c52` : l'ancien test attendait encore `PASS` pour un effet LIVE ; 1 test échoué sur 7. Le commit tests `96dbd189` a corrigé cette attente et ajouté les régressions HTTP. Le HEAD final testé est vert.
- L'ajout de cette section a produit le commit documentaire `d13f5e944c7f14d8114322f720119d527f6e850c`, validé par [PR CI #40664618475](https://github.com/alimtalbi-ata/aiops/actions/runs/40664618475) et [push CI #40664610523](https://github.com/alimtalbi-ata/aiops/actions/runs/40664610523) : `completed/success`, jobs `policy-and-static` et `grafana-real-integration` success, aucune étape en échec.

## Fusion et qualification post-fusion

- [PR #118](https://github.com/alimtalbi-ata/aiops/pull/118) fusionnée par squash dans `main` au SHA **`b33f655695949d6fef9e7d72b537d9810859c494`**, après vérification du HEAD, des checks, des 14 tests Policy (dont 3 HTTP) et de l'état GitHub `mergeable=true`, `mergeable_state=clean`.
- [CI post-fusion #40664759313](https://github.com/alimtalbi-ata/aiops/actions/runs/40664759313) : `completed/success` sur le SHA de fusion ; jobs `policy-and-static` et `grafana-real-integration` réussis, aucune étape échouée.
- Ancienne PR #76 fermée comme doublon après commentaire explicatif ; aucune branche ni travail tiers écrasé.
- Ce complément documentaire est livré dans une PR séparée ; ses propres checks restent à vérifier avant fusion. Aucun déploiement, aucun effet LIVE.
