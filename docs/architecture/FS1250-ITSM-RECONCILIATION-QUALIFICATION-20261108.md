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
| `integration/glpi_copilot_bridge.py` | GET tickets/suivis et POST ITILFollowup ; marqueurs de réponse Copilot | Dépend de `portal.glpi_client.GLPIClient`, module absent du dépôt. Pas de création Ticket ni publication xref. Le suivi ne vaut pas réconciliation. |
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

## Correctif minimal effectivement livré

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

## Qualification exécutée et limites

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
