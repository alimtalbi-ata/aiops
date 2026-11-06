# Rapport de qualification — FS-001D / Worker Temporal guarded DEMO

**Date :** 2026-11-06  
**Statut :** qualification E2E DEMO isolée **PASS** ; **pas de qualification LIVE ni de déploiement production**  
**PR associée :** [#446](https://github.com/alimtalbi-ata/aiops/pull/446) (draft, revue requise)

## 1. Périmètre et méthode

Exécutions attestées par les sorties console de SRV-DEB-05 transmises lors de la qualification. Les scripts de preuve sont versionnés dans `scripts/fs/` et cités ci-dessous. Les runs ont été créés dans le Core du réseau Docker E2E `aiops2-e2e-v1_control`, sur une file Temporal de test indépendante ; aucun Worker permanent n'a été remplacé. Les résultats rapportés ci-dessous sont des **observations de test**, non une preuve que les gardes couvrent toutes les courses, redémarrages, effets externes et combinaisons d'entrées.

| Test | Artefact / commit | Résultat observé | Portée |
|---|---|---|---|
| FS.993 | [script](../../scripts/fs/FS.993.sh), commit `d012786ff56a6f5bd0d4556462c5a6a2a2326818` | **PASS** | Workflow Temporal réel en mode LIVE synthétique, bloqué à NORMALIZE ; absence d'adaptateurs LIVE qualifiés |
| FS.994 | [script](../../scripts/fs/FS.994.sh), commit `8378c2097fae6642fa5c49f7e8afc91766eb64d5` | **FAIL de l'assertion attendue**, workflow **RESOLVED** | Le test supposait à tort que DEMO devait être BLOCKED avant REMEDIATE |
| FS.995 | [script](../../scripts/fs/FS.995.sh), commit corrigé `39888f981d17778863373d9580f18f7735c9c8aa` | **PASS** | Audit en lecture seule de FS.994 : Policy = PASS / SIMULATE |
| FS.996 | [script](../../scripts/fs/FS.996.sh), commit `46d67602f8d7d115eca7570a0546c10c96340ec0` | **PASS** | Vérification de provenance synthétique HITL/REMEDIATE/VERIFY et inspection des branches de code |
| FS.997 | [script](../../scripts/fs/FS.997.sh), commit `b779b4acb3a2ef9d850e1b6ddc7c8eba5aabd456` | **PASS build** | Image expérimentale durcie créée localement, sans déploiement |
| FS.998 | [script](../../scripts/fs/FS.998.sh), commit corrigé `846f9b2b499df85df9c574fcbb485ce7864382ef` | **14/14 PASS** | Tests offline du verrou avant REMEDIATE et VERIFY |
| FS.999 | [script](../../scripts/fs/FS.999.sh), commit `83456e6e087371e2c4f5937aa705f29ca21d5805` | **PASS** | Workflow Temporal DEMO réel sur image FS.997, final RESOLVED |

## 2. Preuves de sécurité LIVE — FS.993

- Run : `RUN-E9768FBFD86E8F25` ; `TEST_MODE=LIVE` (run de qualification synthétique, aucun adaptateur LIVE exécuté).
- `NETWORK_ISOLATION=PASS` et `REAL_INCIDENT_WORKFLOW_STARTED=YES`.
- `TEMPORAL_RESULT_STATUS=BLOCKED` et `CORE_RUN_STATUS=BLOCKED`.
- `LIVE_ADAPTER_UNAVAILABLE_EVENTS=1` ; étapes observées : `INGEST,RUN,NORMALIZE`.
- `PRODUCTION_RESTARTED=NO`, `EXISTING_E2E_WORKER_UNCHANGED=YES`.

**Interprétation limitée :** le chemin LIVE testé échoue en mode fermé à NORMALIZE. Cela ne valide ni des adaptateurs LIVE réels ni la sécurité de toutes les reprises possibles.

## 3. Correction du diagnostic DEMO — FS.994/995/996

- Run de référence : `RUN-171493F5FE80D45E` ; scénario `SCN-GOLDEN-PAYMENT-P1` ; mode `DEMO`.
- FS.994 observait `RESOLVED`, avec passage par `POLICY,HITL,REMEDIATE,VERIFY,RECONCILE,LEARN`. L'assertion de blocage dans le test était erronée pour ce scénario.
- FS.995 a identifié la gate `POLICY state=PASS decision=SIMULATE`, raison : « critic validated and evidence fresh; no production mutation permitted » ; Critic `validated=true`, confiance diagnostique `0.93`.
- FS.996 a confirmé `synthetic=true` sur les événements `STAGE_COMPLETED` de `HITL`, `REMEDIATE` et `VERIFY`.

**Limite :** un marqueur `synthetic=true` et une décision `SIMULATE` ne constituent pas une preuve exhaustive d'absence d'effets externes ; le test comporte des écritures dans les **services E2E** (Core, Twin, Evidence).

## 4. Durcissement expérimental — FS.997

- Image locale testée : `aiops2-worker:fs997-demo-gate-hardened-20261106`.
- SHA256 de `/app/worker/main.py` : `dfa580bb4caeea2e4815f8c3ab560e3b0d54b44fb5dc3abc38b4a3f56cbc8327`.
- Un verrou additionnel vérifie, avant `REMEDIATE` et `VERIFY`, que le run Core et l'activité sont en `DEMO`, que le scénario correspond et qu'une gate Policy `PASS / SIMULATE` existe.
- File Temporal configurable, trois sites d'utilisation conservés.
- **La modification est produite par le script FS.997 et injectée dans une image locale. Elle n'est pas équivalente à un patch directement intégré/revu dans le fichier `app/worker/main.py` du dépôt.** Ne pas déclarer que ce code est livré en production.

**Risque restant :** lors d'une autorisation manquante, le verrou déclenche une exception. Les transitions terminales et comportements de retry Temporal doivent être vérifiés ; il ne s'agit pas automatiquement d'une commande Core `BLOCK`.

## 5. Contrats offline — FS.998

Sur le code extrait de l'image FS.997, pour chacune des étapes `REMEDIATE` et `VERIFY` :

| Cas | Résultat attendu et observé |
|---|---|
| Gate absente | DENY |
| Gate BLOCKED | DENY |
| Gate PASS / EXECUTE (non SIMULATE) | DENY |
| Scénario incohérent | DENY |
| Mode du run incohérent | DENY |
| Mode de l'activité incohérent | DENY |
| DEMO, scénario cohérent, PASS / SIMULATE | ALLOW |

**`GATE_CONTRACT_CASES=14`**, **`GATE_CONTRACT_RESULT=PASS`**, `HTTP_WRITES=0`, `NEW_WORKFLOWS_STARTED=0`.

**Limite :** le test exécute le nœud de garde issu de l'AST avec un Core simulé en mémoire ; il ne couvre pas les erreurs réseau, réponses malformées, courses ou mutations entre la lecture et l'action.

## 6. Parcours métier E2E durci — FS.999

- Run : `RUN-010446A2C20AD203` ; `SCN-GOLDEN-PAYMENT-P1`, synthétique.
- `NETWORK_ISOLATION=PASS` ; `REAL_INCIDENT_WORKFLOW_STARTED=YES`.
- `TEMPORAL_RESULT_STATUS=RESOLVED` ; `CORE_RUN_STATUS=RESOLVED`.
- Étapes observées : `INGEST,RUN,NORMALIZE,CORRELATE,CMDB,OBSERVE,RAG,DGX_ANALYST,DGX_CRITIC,POLICY,HITL,REMEDIATE,VERIFY,RECONCILE,LEARN`.
- `POLICY_SIMULATE=PASS` ; `SYNTHETIC_STAGE=HITL:PASS`, `REMEDIATE:PASS`, `VERIFY:PASS`.
- `HARDENED_DEMO_WORKFLOW_E2E=PASS` ; `PRODUCTION_RESTARTED=NO`, `EXISTING_E2E_WORKER_UNCHANGED=YES`.

**Interprétation :** la simulation autorisée fonctionne jusqu'au bout avec le Worker durci, sans régression constatée sur ce scénario.

## 7. Revue PR #446 — à solder AVANT décision de merge

La PR #446 est **draft**. Sa description historique parle d'un artefact `.diff` en revue seulement ; la liste actuelle des fichiers modifiés comporte aussi `app/worker/main.py` et de nombreux scripts de qualification. Il faut aligner description, portée et diffs avant toute approbation.

- [ ] Rebaser/extraire si nécessaire les changements applicatifs dans une PR à périmètre clair ; ne pas mélanger garde d'exécution FS-001A, artefacts FS-001B/FS-001D et chantier portail sans revue explicite.
- [ ] Comparer `app/worker/main.py` du dépôt à la **source de runtime réellement déployée** et à l'image FS.997 ; ne pas conclure sur la seule réussite d'une image locale.
- [ ] Vérifier le garde `/api/execution/start` contre : `BLOCKED`, `WAITING` légitime, `404`, indisponibilité Core, duplicata, courses Core/Temporal et idempotence.
- [ ] Vérifier que le garde DEMO refuse en E2E l'absence de `PASS/SIMULATE`, y compris récupération d'erreur et état terminal du run.
- [ ] Tester les garanties de non-remédiation réelle et les effets externes (réseau, adaptateurs, écritures) au-delà des marqueurs `synthetic`.
- [ ] Exécuter tests/CI sur le commit final, joindre les sorties expurgées de secrets et vérifier la stratégie de rollback.
- [ ] **Ne pas** fusionner, sortir du mode draft, redémarrer la production ou déployer le Worker LIVE sans autorisation explicite et validation complémentaire.

## 8. Décision proposée

**ACCEPTÉ :** qualification de l'image FS.997 pour **ce parcours DEMO synthétique et isolé**.  
**NON ACCEPTÉ :** qualification LIVE, déploiement en production, garantie d'absence absolue d'effets externes, approbation de merge PR #446.

## 9. Suite — portail et démo observabilité

L'inventaire FS.1000 (partiel, première exécution arrêtée par des permissions sur `reports`) montre un portail existant, Prometheus, Grafana, Alertmanager, Loki, Tempo, OTel, PostgreSQL, MariaDB et GLPI. Réutiliser ces services, sans installer de stack parallèle. Voir le plan [portail/observabilité/CMDB](../roadmap/AIOPS-DEMO-OBSERVABILITY-PORTAL-2026-11-06.md). Les contrats API restent à confirmer par FS.1000 corrigé.
