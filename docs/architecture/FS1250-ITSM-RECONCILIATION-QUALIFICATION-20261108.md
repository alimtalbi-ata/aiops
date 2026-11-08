# FS1250 — cartographie et qualification du correctif d'audit

Date : 2026-11-08. Responsable : Core / Integration.
Base inspectée : `audit/preserve-debian-48h-20261108@8fb36639dd5794f8bd468f458d047572a2118579`.
Candidat : branche `fix/fs1250-itsm-identity-audit`, SHA exact fourni par la PR.
Documents de continuité, décisions et workpackages lus avant modification.

## Conclusion et niveau de preuve

**HOLD pour la réconciliation persistante ; correctif des vérifications livré.**
La continuité rapporte GLPI #201 pour `RUN-8CA56A39E58944F1` /
`INC-FS1250-AUTOGLPI-625916362ACD42C9`, sans ligne Core ni événement xref.
Le ticket n'a pas été relu dans cette session. Son existence est une observation
UI rapportée, pas une attestation API indépendante. Aucune nouvelle création
n'est nécessaire pour réparer une liaison avec un ticket existant.

La discontinuité observée est entre l'effet GLPI et sa projection Core. Le point
exact de perte (émission absente, mauvais destinataire, rejet d'identité,
consommateur arrêté, transaction échouée) reste UNKNOWN : le producteur FS1250,
le consommateur FS1130/FS1250 et leurs migrations ne sont pas dans cette branche.
Les réinventer ici produirait un second chemin d'écriture non qualifié.

## Code réellement présent : producteurs, consommateurs, persistance

| Source | Production / consommation effective | Limite |
|---|---|---|
| `integration/n8n/incident-to-run.json` | Webhook → POST Core incidents → runs → execute | Import manuel, workflow inactif ; aucun appel GLPI ni événement xref. Configuration d'auth historique à requalifier avant import ; ne pas l'exécuter. |
| `app/core/main.py` | Incident : `INC-` + external_id ; Run : ID généré ; `RUN_CREATED`, `STATE_TRANSITION`, endpoint events → `aiops.run_events` | Ni création de ticket, ni route de consommation xref, ni tables GLPI. |
| `app/worker/main.py` | Temporal `IncidentWorkflow`, workflow_id=run_id ; activités POST events/gates/checkpoint/evidence | STAGE_STARTED/COMPLETED/FAILED, GATE_BLOCKED et LIVE_ADAPTER_UNAVAILABLE ; étape RECONCILE générique synthétique, pas une liaison GLPI. LIVE bloqué. |
| `db/migrations/000–008` | Tables canoniques et unicité `(run_id,event_key)` dans 008 | Ni `glpi_ticket_links`, ni `itsm_xref_events`, ni `critic_denial_outbox` ; l'unicité des run_events ne prouve pas celle des xrefs. |
| `integration/glpi_copilot_bridge.py` | GET tickets/suivis et POST ITILFollowup ; marqueurs de réponse Copilot | Dépend de `portal.glpi_client.GLPIClient`, module absent de cet arbre d’audit mais présent dans une autre branche (voir revue ci-dessous). Pas de création Ticket ni publication xref. Le suivi ne vaut pas réconciliation. |
| `app/portal/glpi_operator_view.py` | Handoff en lecture seule ; UNKNOWN / NOT_INSTALLED | Aucun appel GLPI/Core pour la liaison ; pas un client GLPI natif. |
| `scripts/ops/glpi_readback_probe.py` | GET natif `/apirest.php/Ticket/{id}` → reçu JSON local | Ni écriture GLPI, ni écriture Core ; jetons par environnement. |
| `scripts/ops/run_linkage_gate.py` | SELECT PostgreSQL READ ONLY + GET Core → rapport local | Dépend du schéma Debian absent ; ses checks GLPI séparés ne suffisent pas à prouver une jointure d'identité. |
| `scripts/ops/itsm_link_diagnosis.py` | Jointure des rapports précédents → diagnostic local | Aucun consommateur durable, aucun backfill, aucune autorisation d'action. JSON d'entrée supposé issu d'une collecte de confiance ; pas de signature. |

Le graphe ITSM démontrable s'arrête donc à :
`producteur déployé UNKNOWN → GLPI #201 (UI rapportée) → événement UNKNOWN → consommateur UNKNOWN → tables Core absentes pour FS1250`.
Le chemin Policy/Critic est distinct : un refus réconcilié ne garantit pas une xref ITSM.

## Divergences avec Debian documenté

Source des observations : dernière section FS1250 de `docs/PROJECT-CONTINUITY.md`
et `docs/operations/SRV-DEB-05-INVENTORY-2026-11-08.md` ; aucune collecte hôte ici.

| Debian rapporté | Branche inspectée | Conséquence |
|---|---|---|
| Core `aiops2-core:fs1212-integrated-candidate` | Core sans KPI GLPI ni route denial-intent/reconciled | Le tag ne prouve aucun SHA ; ne pas remplacer cette image par le code de cette branche. |
| Worker `aiops2-worker:fs-demo-candidate-20261105` | Worker générique Temporal, sans client GLPI | Producteur réel du ticket non identifié. |
| GLPI `glpi/glpi:11.0.9`, API native opérationnelle selon continuité | Probe de cette API disponible | Réutiliser cette API ; aucune nouvelle API. |
| 44 liaisons FS1130 CONFIRMED, zéro pending/failed ; xref vide | Schéma / writer absents | Préserver ces 44 lignes ; impossible de qualifier leur persistance avec ce checkout. |
| Run BLOCKED, refus Critic réconcilié, décision `POL-0CB0E84ECD6E01B0` | Pas de denial outbox dans les migrations | Ne jamais rejouer l'exécution ou assouplir Policy pour réparer ITSM. |

Les digests, commits de build, overlays effectifs et sources sales restent UNKNOWN.
Cinq projets Compose sont documentés ; le nom d'un conteneur ne suffit pas à
identifier son projet. Aucune image n'est qualifiée par cette analyse de source.

## Correctif initial livré au commit 2305759 (révisé ci-dessous)

1. Le probe exige l'ID numérique retourné égal au ticket demandé, un ticket non
   supprimé et les deux marqueurs exacts Run + Incident. Les préfixes/suffixes
   d'autres identifiants ne passent plus. Le nom `MATCHED_MARKER` reste compatible
   mais signifie seulement correspondance des marqueurs, jamais liaison durable.
2. Le diagnostic compare Run du rapport et Run DB, Incident DB et Incident de
   chaque lien/xref, puis enveloppe et ticket de tout readback fourni. Il refuse
   les doublons de lien, les liaisons concurrentes et un readback contradictoire.
   Les anciens rapports sans identité suffisante doivent être recollectés.
3. Tests ajoutés aux déclencheurs push/PR et à l'exécution CI d'audit existante.
   Un test Policy explicite conserve le refus Critic même pour LIVE OBSERVE.

Aucune mutation de données métier : les 44 liaisons réelles et le refus déployé
ne sont pas touchés. Le test des 44 liaisons utilise exclusivement des fixtures
synthétiques, pas une copie ni une attestation du contenu Debian.

## Correctif persistant proposé, à porter dans le consommateur existant

Prérequis : retrouver le source/build exact du writer, le contrat de livraison,
le consommateur, le DDL/index réel et son mécanisme de verrouillage ; préserver
images/sources/configuration/données et rollback avant toute promotion.

- Relire #201 et le contrôle positif #199 via l'API native authentifiée ; vérifier
  ID retourné, Incident/Run, entité et périmètre d'autorisation. #200/FS1233 reste
  un second contrôle indépendant. Un simple marqueur est une piste : plusieurs
  candidats ou identités contradictoires imposent HOLD et revue humaine.
- Réutiliser le chemin existant de rapprochement d'un ticket déjà présent. Aucun
  fallback vers création Ticket ; aucun SQL direct de réparation sur Debian.
- Dans une transaction Core, revalider le lien canonique Run→Incident, verrouiller
  la clé d'identité selon le schéma réel et appliquer la clé idempotente existante.
  Même triplet déjà confirmé : no-op avec reçu stable ; autre ticket ou ticket
  possédé par une autre identité : conflit explicite, jamais overwrite.
- Inscrire l'événement xref auditable et sa projection de lien de façon atomique,
  puis acquitter la livraison après commit. Si le contrat utilise une outbox,
  reprendre son protocole au lieu d'en créer une seconde. Run BLOCKED et décision
  Critic/Policy restent inchangés. Aucune migration proposée sans DDL réel.
- Tester sur PostgreSQL isolé : deux livraisons, deux workers concurrents, arrêt
  après effet GLPI avant commit, arrêt après commit avant ACK, rollback transaction,
  identités étrangères, candidats multiples, indisponibilité/API 401 et préservation
  exacte des 44 liens. Vérifier une seule projection et le nombre d'événements
  attendu par le contrat existant. **Ces tests durables ne sont pas exécutables
  sur cette branche sans les composants absents ; ils ne sont pas déclarés PASS.**

## Qualification initiale au commit 2305759 et limites

Environnement Cloud local, Python 3.12 ; aucun service Debian/GLPI/PostgreSQL appelé.

| Commande | Résultat |
|---|---|
| `python -m unittest discover -s tests/ops -v` | 47 tests, OK |
| `python -m unittest discover -s tests -p test_policy_safety.py -v` | 15 tests, OK |
| `python -m unittest discover -s tests -p test_simulation_policy_contract.py -v` | 6 tests, OK |
| `python -m py_compile scripts/ops/glpi_readback_probe.py scripts/ops/itsm_link_diagnosis.py` | PASS |
| `git diff --check` | PASS |

68 tests locaux : unitaires/contrats, avec HTTP Policy en mémoire. Aucun test ignoré
par ces commandes. Une dépréciation Starlette/httpx est émise, sans échec.
Les lignes FAILURE/health affichées par certains tests ops sont des scénarios
négatifs synthétiques ; le bilan unittest fait foi. CI distante non attestée ici.
Intégration PG, E2E authentifié, readback réel, concurrence durable, install/rollback
et qualification Debian : **NON EXÉCUTÉS**. Ne pas transformer ce bilan en E2E PASS.

Risque : diagnostics plus stricts, anciens reçus à recollecter ; le vrai défaut
persistant demeure non réparé. Debian installé : **non par cette livraison**.
Rollback source : revert de ce seul candidat ; aucune migration/data à annuler.
Ne pas restaurer un ancien verdict PASS sans vérifier les identités.
La promotion et toute réparation persistante restent HOLD, sous approbation
opérationnelle distincte après les preuves manquantes. Aucun ticket, déploiement,
cron, redémarrage, merge ou commande de remédiation exécuté.


## Revue PR #455 — identités, preuves et inventaire transversal

Cette section remplace les conclusions initiales qui pouvaient assimiler les
booléens DB à une preuve indépendante ou l'absence dans l'audit à une absence
globale du projet. Pas de nouvelle PR, pas de merge, pas d'écriture GLPI/PG.

### Comparaison de branches et préservation

Base initiale : `8fb36639dd5794f8bd468f458d047572a2118579`.
Audit comparé : `2205c74` (après `6765ba0`). Les deux commits ajoutent uniquement
`docs/architecture/AIOPS2-GITHUB-REUSE-INVENTORY-2026-11-08.md`.
Ce document a été repris intégralement, sans rebase ni merge de branches, sur la
branche existante de #455. Blob de référence et copie :
`e65af74cb3873276fb5aa0137e8631d6c2695c72` ; diff du fichier contre l'audit : vide.
Les ajouts d'inventaire ne sont ni supprimés ni réécrits.

### Implémentations réellement retrouvées et lues

| Source exacte inspectée | Code / dépendances / limites |
|---|---|
| `feat/glpi-ai-ticket-enrichment-e2e@5b3b9f327f517e8f5999766389abf69c8a035cf8` | `app/portal/glpi_client.py` (blob `8cd3cd2381356e23d777dd6c0087ac03bd9b7375`) : sessions natives, GET/search, create/update, lookup par Run. Dépend de requests et de credentials serveur. `glpi_run_context.py` possède déjà `/api/internal/glpi/runs/{run_id}/sync` : lookup → update ou création → readback de rapport. C'est un writer candidat existant ; aucun appel ni portage de ce chemin mutateur ici. Son lookup utilise une sous-chaîne de titre, pas une liaison structurée tenant/instance/Incident/Run. Ni son déploiement ni son rôle dans FS1250 ne sont établis. |
| `fix/core-xref-glpi-readback-gate-20261101@00dd0443d4d36d7aeb36bb77490777ac6ef5785d` | `app/core/itsm_xref.py` (blob `c59c2a281be351ce61064269dbc65bc4b689d9aa`) : router intégré à Core, ACL serveur tenant/instance/ticket, historique signé/supersession, ownership indépendamment attesté, relecture native HTTPS Ticket/Entity/CI, Run→Incident DB. Dépend de `shared.db`, FastAPI, requests, clés/config serveur et schéma migration `012_itsm_xref_read.sql`. Migration append-only, source_event_id unique, unicité tenant/instance/ticket/version ; aucun `glpi_ticket_links` créé par cette migration. Ne pas appliquer sur le schéma Debian inconnu. Le module ne confond pas HMAC/verified=true et preuve GLPI : `_glpi_readback` est obligatoire. Réemploi à qualifier, pas une nouvelle API à développer. |
| PR [#454](https://github.com/alimtalbi-ata/aiops/pull/454), `core/fs147-fs1250-reconcile-20261108@87f0c5746a9d78f1e3696ecfe73bbeea8278eefb` | Draft, non fusionnée à l'inspection. `app/core/itsm_reconcile_contract.py` distingue MATCHED/EXISTING_UNLINKED/AMBIGUOUS/UNKNOWN/CONFLICT ; gates de lineage, admission et reçus également présents. Classificateurs purs, basés sur des claims et booléens fournis : ils ne réalisent pas eux-mêmes un readback authentifié ni une réparation durable. Ne pas les présenter comme preuve source/API. |

L'absence est donc **locale à l'arbre d'audit** pour ces composants. Leur présence
dans d'autres branches est confirmée par lecture du source. La correspondance
avec les images Debian, le writer FS1250 réellement exécuté et la chaîne
persistante déployée restent UNKNOWN. Les tests de ces branches tierces n'ont
pas été exécutés par cette revue ; aucune qualification croisée n'est revendiquée.

### Comportement corrigé du diagnostic

- Contrat `aiops2-itsm-link-diagnosis-v2`, toujours `HOLD`. Aucun chemin
  `LINK_VERIFIED`/`PASS` : un outil hors ligne ne peut authentifier les fichiers
  fournis. Un JSON cohérent devient au mieux `LINK_CONSISTENT_UNATTESTED`, même
  avec `authenticated=true`, `signature_verified=true` ou verified=true en DB.
  Une signature déclarée n'est pas une signature vérifiée.
- Jointure explicite Run/Incident/ticket ; comparaison des claims tenant et
  instance GLPI dans le rapport, Run DB, liens, xrefs et enveloppe du readback.
  Les claims contradictoires dans le ticket lui-même sont aussi refusés.
  Scope ou run_id xref manquant : identité non vérifiée. Le collecteur existant
  omet ces champs : ses anciens reçus restent donc HOLD, sans inventer le DDL.
- Plus d'un xref : `AMBIGUOUS_XREFS`, même si les lignes sont identiques ou une
  ligne est vérifiée. Ni sélection arbitraire, ni effacement de doublons, ni
  interprétation locale d'un historique avec révocation/supersession. Le Core
  existant possède un contrat d'historique à qualifier pour cela.
- Rapports malformés, ticket booléen/flottant/null/zéro, scopes étrangers,
  readback erroné/401, liens concurrents : HOLD. Les contrôles n'écrivent que le
  diagnostic local demandé ; aucune mutation des entrées ni donnée métier.

L'outil ne dispose actuellement d'aucun vérificateur indépendant de transport,
signature, fraîcheur, ACL ou ownership pour ces fichiers ; ajouter des champs
JSON ne le transforme pas en vérificateur. Pour une future qualification positive,
réutiliser la lecture Core xref existante après contrôle de provenance/configuration
et tests d'intégration. Ne pas créer un second client/endpoint d'attestation.

### Tests de revue et qualification finale

Commandes de validation, à réexécuter après le commit final sans retoucher son arbre :

| Commande | Résultat local de la revue |
|---|---|
| `python -m unittest discover -s tests/ops -v` | 62 tests OK, dont 26 tests du diagnostic (plusieurs matrices négatives par sous-cas) |
| `python -m unittest discover -s tests -p test_policy_safety.py -v` | 15 tests OK |
| `python -m unittest discover -s tests -p test_simulation_policy_contract.py -v` | 6 tests OK |
| `python -m py_compile scripts/ops/glpi_readback_probe.py scripts/ops/itsm_link_diagnosis.py` | PASS |
| `git diff --check` | PASS |

Total : **83 tests locaux**. Les 44 fixtures synthétiques sont rejouées sans
mutation et restent HOLD faute de preuve API indépendante. Cela ne qualifie ni
les 44 lignes réelles ni l'idempotence d'une écriture durable.
Le SHA final et la réexécution exacte sont consignés dans la description de la
PR #455 après validation, pour éviter une auto-référence SHA dans ce document.
CI distante non attestée par ce bilan ; dépréciation Starlette/httpx sans échec.
Readback réel, PG16 transactionnel/concurrent, E2E et qualification Debian :
**NON EXÉCUTÉS / HOLD**. Aucun merge, écriture GLPI/PostgreSQL ou déploiement.
Rollback : revert du correctif de revue uniquement, sans supprimer le document
d'inventaire transversal ni restaurer les faux PASS. Aucun rollback de données.
