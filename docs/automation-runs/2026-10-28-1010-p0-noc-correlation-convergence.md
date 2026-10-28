# P0 NOC — convergence de la corrélation tenant/LIVE

- **Date / créneau :** 2026-10-28, 10:09–10:13 Europe/Paris (horaire de préparation ; validation finale consignée sur la PR).
- **Dépôt / branche :** `alimtalbi-ata/aiops`, `fix/p0-noc-correlation-tenant-live-converge-20261028-1010`.
- **HEAD main vérifié avant écriture :** `99403bd5e38f4d5dc4f5c7bc5ad36f760a5570cc`.
- **PR draft :** https://github.com/alimtalbi-ata/aiops/pull/116
- **Commits code / tests :** `4aa8735c96f2a3c7bc4cf2039478afd1a4a71a02`, `ee23bb3bf62657891ee3c1067e3280a8a9cdf3a4`.
- **Fichiers :** `app/portal/noc_correlation.py`, `tests/test_noc_canonical_correlation.py`, ce journal.

## Lecture et décision

Lecture du HEAD main, de `README.md`, `docs/PROJECT-CONTINUITY.md`, architecture, décisions, catalogue de réutilisation, protocole de qualification, `quality.yml`, des PR ouvertes #36/#37/#39/#41/#43 et des PR NOC #75/#83. PR #36 : lecture ciblée de `demo/noc_livestatus_import.py` et `demo/rag_ops_fixture_catalog.json` ; leurs données et parseurs restent synthétiques/offline et ne prouvent aucune intégration Checkmk. La fixture RAG de #36 est déjà portée dans main : pas de réimport ni de merge massif. Portage ciblé de l'intention de #75 sur le HEAD actuel, avec réutilisation du garde-fou récursif `noc_runtime._reject_unqualified_tenant_scope` de main plutôt que la liste partielle de #75.

## Changement de comportement

La corrélation signée NOC ↔ Run Core refuse désormais les Runs `LIVE` et les métadonnées de portée tenant/org/workspace/account, y compris alias imbriqués et valeurs nulles, des **deux** côtés. Aucune signature HMAC ni identité Run ne vaut autorisation tenant. Les modes DEMO/REPLAY/STORY sans portée tenant restent des correspondances **synthétiques non attestées**. Erreurs HTTP 503 génériques, `no-store`, sans identifiant privé dans la réponse. Pas d'écriture Core, ni d'effet de remédiation.

## Tests, provenance et limites

- **Contrats négatifs ajoutés :** refus LIVE même sur IDs exacts ; champs tenant/org/account/workspace aliasés et imbriqués dans NOC et Core, y compris `null` ; HTTP 503, absence de fuite, `no-store`.
- **Non-régression :** DEMO/REPLAY/STORY conservent `SYNTHETIC_CANONICAL_RUN` sans attestation.
- **CI existante :** `.github/workflows/quality.yml`, déclenchée par push et PR ; exécutions https://github.com/alimtalbi-ata/aiops/actions/runs/40662288755 et https://github.com/alimtalbi-ata/aiops/actions/runs/40662305291. **PENDING au moment de la rédaction** : ne pas interpréter comme PASS. Consulter les jobs et l'état final sur la PR.
- **Local :** `git ls-remote` impossible (résolution DNS github.com indisponible) ; pas de test local revendiqué.
- **NOT_TESTED/BLOCKED :** Core/PostgreSQL réel avec ACL tenant A/B ; Checkmk/Thruk réels ; métriques Grafana liées à Incident/Run ; diagnostic Ollama 4B/NGX 192B ; captures authentifiées et vidéo ; déploiement Debian et toute preuve LIVE. Les jobs Grafana éphémères de `quality.yml`, s'ils réussissent, attestent seulement la santé HTTP Grafana.
- **Risque résiduel :** garde-fou conservateur, **pas** un RBAC tenant. La décision ACL doit être prise côté Core avec acteur/tenant authentifiés ; le refus des champs n'établit pas l'absence de tenant hors contrat. Les intégrations ne doivent pas présenter les données synthétiques comme observées.
- **Retour arrière :** revert ciblé de la PR sur GitHub après revue, aucun changement de runtime.

## Prochain micro-lot

Qualifier l'identité tenant A/B et le refus cross-tenant côté Core avec vrai service Core/PostgreSQL éphémères en CI ; puis corréler les observations Checkmk/Thruk et métriques Grafana en lecture seule avec provenance et fraîcheur. Ne jamais appeler le NGX réel en CI, et utiliser Ollama 4B uniquement sous `CI_SIMULATED_LLM` si l'adaptateur LLM est effectivement testé.
