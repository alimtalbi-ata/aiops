# AIOps2 — consolidation des développements parallèles (2026-11-09)

**Statut : inventaire d'intégration, sans déploiement.** Référence de comparaison : runtime observé sur SRV-DEB-05, pas la branche GitHub seule. Ne pas merger en bloc les branches divergentes.

## Faits vérifiés

- Core PG : 137 RUN (52 RUNNING, 48 RESOLVED, 29 BLOCKED, 8 CREATED), tous DEMO lors du relevé. `RESOLVED` ne prouve pas un effet LIVE.
- GLPI : `aiops.glpi_ticket_links` a pour identité `incident_id` (pas `run_id`), `glpi_ticket_id`, `state`, `confirmed_at`. Des liens FS1130 sont CONFIRMED. Deux RUN Temporal bloqués n'ont pas de lien dans cette table.
- Temporal : RUN-8CA56A39E58944F1 et RUN-C3BD568B15367B66 ont des activités achevées ; Core les classe BLOCKED, le second au Critic/HUMAN_APPROVAL.
- Worker Debian : SHA256 de `/app/worker/main.py` = `ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda` ; distinct de l'image FS.997 qualifiée (`dfa580bb4caeea2e4815f8c3ab560e3b0d54b44fb5dc3abc38b4a3f56cbc8327`).
- Worker Debian : garde `/api/execution/start` déjà présent (Core CREATED/WAITING), reprise durable des refus Critic, preuves FS, Policy, et blocage `FS_STAGE_NOT_QUALIFIED` sur POLICY/HITL/REMEDIATE/VERIFY/RECONCILE/LEARN pour scénarios FS.
- Qualification parallèle FS.999 (PR #446) : vrai IncidentWorkflow Temporal, RUN-010446A2C20AD203, scénario SCN-GOLDEN-PAYMENT-P1, DEMO, Policy PASS/SIMULATE, HITL/REMEDIATE/VERIFY synthétiques PASS, Temporal/Core RESOLVED, environnement E2E isolé. Pas de LIVE, pas de déploiement.

## Matrice d'intégration sélective

| Domaine | Source de progrès | Déjà disponible | Delta à traiter |
|---|---|---|---|
| Worker/Temporal | PR #446, FS.997–FS.999 | Ingress Core, refus Critic durable, blocage FS | Comparer les conditions de garde avant REMEDIATE/VERIFY ; ne reprendre que les conditions absentes et compatibles avec le runtime FS |
| Core/Policy/HITL | PR #466, #450 | Gates Policy et décisions Core observées | Revue des invariants action/tenant/fencing et de la reprise WAITING ; ne pas dupliquer l'autorité |
| GLPI | PR #192, client Portal existant | Liens durables par incident_id, tickets FS1130 confirmés | Corrélation et lecture authentifiée des tickets existants ; ne pas créer un second client/writer |
| ITSM | PR #454 | Liens et mécanisme de réconciliation historiques | Évaluer le classificateur en lecture seule avant éventuelle adoption |
| Coordination | PR #468 | Tests Debian 15/15 | Éviter que `glpi_handoff_consumer.py` devienne un deuxième consommateur opérationnel ; conserver uniquement les adaptateurs réellement nécessaires |

## Règles de reprise

1. **Runtime d'abord** : le Worker monté sur Debian comporte des ajouts FS absents de certaines branches ; ne jamais le remplacer par `app/worker/main.py` d'une branche historique.
2. **Aucune levée automatique du blocage FS** : `FS_STAGE_NOT_QUALIFIED` est une barrière de sécurité, pas une régression à effacer.
3. **Séparer les scénarios** : FS.999 qualifie un DEMO SAN synthétique, pas un workflow FS ni un effet LIVE.
4. **Éviter les doublons** : GLPI client, xref durable, refus Critic, garde Worker et autorité HITL sont des fonctionnalités existantes.
5. **Livrer par patch ciblé** avec tests du delta, provenance SHA, et revue avant merge/deploy. Ne pas utiliser le statut Core RESOLVED comme preuve de remédiation LIVE.

## Prochaine opération de développement

Comparer les blocs de garde de `_execute_stage_blocking` (FS.997 / runtime Debian), et les chemins `POLICY`, `HITL`, `REMEDIATE`, `VERIFY` de `app/worker/workflow.py` ; établir le delta de logique exact avant d'écrire un patch. La source complète du fichier monté Debian et son mapping vers un commit GitHub restent à identifier : **pas de remplacement à l'aveugle**.

Références : [PR #446](https://github.com/alimtalbi-ata/aiops/pull/446), [rapport FS-001D](https://github.com/alimtalbi-ata/aiops/blob/fix/fs-001a-worker-execution-guard-review/docs/qualification/FS-001D-WORKER-QUALIFICATION-2026-11-06.md), [PR #468](https://github.com/alimtalbi-ata/aiops/pull/468).
