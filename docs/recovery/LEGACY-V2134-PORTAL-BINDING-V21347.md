# V2.13.47 — Hybrid Replay V2.13.4 → cinématique STAR (offline)

**Statut :** adaptateur Python sans accès réseau, testé sur données synthétiques. Aucune modification du portail :17777 ni capture Debian. La PR #36 reste en draft.

## Patrimoine réutilisé sans duplication

| Original / version | Chemin / empreinte SHA-256 | Décision |
|---|---|---|
| AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip / V2.13.4 | `tools/build_real_replay.py` / `f71a568f4229402a6f6b5238552efbdd18fa41320c8c285afedc386812bbb97d` | Original complet déjà inventorié ; conserver en quarantaine, ne pas exécuter sur exports opérateur. |
| Même archive / V2.13.4 | `tools/assemble_hybrid.py` / `ffce55bf4c100642e751e73857a90e50b6f9bc030e4caba8f2bc71268db437d3` | Déjà dans `recovery/legacy_v2134/tools/assemble_hybrid.py` ; ne pas recopier. |
| AIOPS-V2.13.6.1-HYBRID-FINAL.zip / V2.13.6.1 | `01-Demo/tools/build_real_replay.py` / même SHA-256 | Doublon identifié dans l'inventaire V2.13.46. |
| Code PR #36 / V2.13.46 | `demo/star_legacy_replay_adapter.py` | Réutilisé directement ; pas de nouveau moteur replay. |
| Code PR #36 / V2.13.x | `demo/star_portal_transport.py`, `demo/star_scene_scripts.py`, `demo/star_snapshot_choreography.py` | Contrats réutilisés : neuf checkpoints et vues exactes. |

Les SHA historiques ont été **revérifiés sur les octets des trois ZIP originaux de la Library le 24 octobre 2026**, sans extraction vers GitHub : V2.13.4 archive `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550` ; V2.13.6.1 archive `0f382f64a3da7ad0e81c3fde33a2c800ea73844f1ea7f38711ab7b17979a5f29` ; V2.13.10 archive `cdca139131dbbac7adb2f811077c25e94dd01899a6ec33c37ea067d26a351d87`. `build_real_replay.py` fait 12 103 octets, SHA `f71a568f4229402a6f6b5238552efbdd18fa41320c8c285afedc386812bbb97d`, identique dans V2.13.4 et V2.13.6.1. `tests/test_replay.py` (1 762 octets) et `tools/assemble_hybrid.py` (2 628 octets) sont également identiques entre les deux archives. Le portail V2.13.10 `portal_demo_public_v21310.py` (1 762 octets) porte le SHA `5bee897914ec958af0f715f24eee229b9f9539a3df5da4f9c43cb8746ad60ee0`. Les sources GitHub de la PR ont été inspectées avant développement. Aucun secret ni contenu des archives n'est publié.

## Besoin métier et HLD/LLD

Relier explicitement une scène ACME STAR à une ligne d'export Core (events, stages, analyses, critiques, policy_decisions), sans transformer cette association déclarée en preuve runtime, HITL, ticket ou clôture.

`bind_replay_to_transport(transport, replay, bindings)` consomme les schémas existants `star-portal-transport-v1` et `star-core-legacy-replay/v1`. Exemple de mapping : `{"detect":{"source":"events","source_index":1}}`. `export_legacy_portal_binding(manifest, root, scenario, run, ledger, evidence, bindings)` compose les adaptateurs existants avec un manifeste local.

Flux : exports DEMO → `build_replay` (identité, références Evidence, SHA256 JSON canonique) → `bind_replay_to_transport` ← `export_storyboard` (manifeste, neuf vues) → document `star-legacy-portal-binding/v1`. Bibliothèque standard Python 3.12, aucun accès API, DB ou conteneur.

Seuls SAN_FABRIC_P1/PAYMENTS_P2 et DEMO/BLOCKED ou DEMO/RESOLVED sont admissibles. Chaque binding doit référencer une ligne existante, unique et de famille compatible avec le checkpoint. Une scène sans référence est `unbound`. Les rapprochements sont `operator_declared_unattested`, **jamais** déduits automatiquement d'un horodatage. Identité contradictoire, famille incompatible, index booléen, source réutilisée, timestamp illisible, état LIVE/HITL revendiqué et digest malformé sont refusés. Les champs privés des entrées ne sont pas recopiés.

## Qualification et limites

Tests locaux effectivement exécutés le 24 octobre : **15 nouveaux tests PASS**, **10 tests existants replay PASS**, **2 tests transport PASS**, compilation Python PASS. Les deux scénarios ont été assemblés offline avec manifestes synthétiques sans captures. CI GitHub à vérifier après publication, et aucune qualification globale ou Debian revendiquée.

Aucune route FastAPI, page :17777, capture n8n/Grafana/GLPI, HITL réelle, clôture métier ou remédiation LIVE n'est créée. Les SHA d'export portent sur JSON canonique, pas sur les octets originaux ni sur une provenance runtime authentifiée. L'intégration au portail reste à faire.

**Rollback :** supprimer de la branche PR le module, ses tests, la CI dédiée et cette note ; aucun état externe n'est modifié. Pas de merge automatique.

## Correctif V2.13.48 — ordre temporel des checkpoints déclarés

Le raccordement replay→STAR refuse désormais un checkpoint lié dont l'horodatage déclaré précède celui d'un checkpoint lié antérieur. Les timestamps ISO-8601 avec fuseau sont comparés comme instants (pas comme chaînes), et les scènes non liées restent explicitement `unbound`. Ce contrôle détecte un mapping incohérent sans prétendre authentifier l'horloge, l'événement, la capture ou l'exécution métier. Tests synthétiques ajoutés : chronologie inversée refusée et horodatages égaux acceptés sans attestation runtime. **17/17 tests de binding locaux réussis** ; CI du commit à vérifier. Aucun déploiement ni changement de production.
