# AIOps — Programme de reconstruction du RAG opérationnel multi-constructeurs

**24 octobre 2026 · Auteur Abdelhalim Talbi · Statut : spécification et corpus de simulation, pas une validation de commandes sur équipements.**

## Travail existant à capitaliser
Les conversations et inventaires d'octobre contiennent déjà des composants `aiops_v1_rag`, `aiops_v1_context`, `aiops_v1_elastic_memory`, `aiops_v1_causal_engine`, `aiops_v1_nim_gateway`, orchestration n8n, CMDB GLPI, monitoring Grafana/Alloy/Loki et une voie Analyst/Critic. Les journaux `Texte collé(20261019-173734).txt` citent explicitement `aiops_v1_rag` ; cela ne démontre **ni** l'existence actuelle d'un index utilisable, **ni** sa couverture constructeur. Récupérer d'abord schémas d'index, chunking, embeddings, vecteurs et documents avant remplacement.

## Corpus cible — sources classées
| Classe | Domaine | Contenu à ingérer / évaluer |
|---|---|---|
| RUNBOOK | SAN | procédure de diagnostic perte de lien FC, ISL, zoning, CRC/invalid words, path redundancy, validation et rollback **simulés** |
| RUNBOOK | Stockage | latence, queue depth, front-end ports, réplication, capacité, thin provisioning et reconstruction |
| RUNBOOK | VMware / Linux | ESXi APD/PDL, chemins SATP/PSP, `multipath -ll`, latence iostat, file system/VM datastore |
| EVENT_CATALOG | Brocade/Broadcom FOS | événements ports FC, link flap, CRC, ISL, fabric segmentation |
| EVENT_CATALOG | Cisco MDS NX-OS | syslog/trap VSAN, FLOGI, port-channel, interface down |
| EVENT_CATALOG | Dell EMC PowerMax | alertes de directors/front-end, SRDF, capacity, latency |
| EVENT_CATALOG | Pure FlashArray/FlashBlade | performance, capacity, volume connectivity, snapshots |
| EVENT_CATALOG | NetApp ONTAP | LIF, aggregates/volumes, SnapMirror, NAS protocol status |
| EVENT_CATALOG | VMware | APD/PDL, HBA, datastore accessibility, vCenter alarm |
| EVENT_CATALOG | RHEL/Linux | kernel SCSI, dm-multipath path fail/reinstate, systemd/journald |
| SNMP_MIB | multi-vendeurs | enterprise OID, version MIB, trap varbinds/types, severity **vendor-specific**, contrôles SNMPv3 |
| TRACE | stack AIOps | OpenTelemetry logs, trace_id, correlation_id, run_id, event_id, parent/child, n8n execution, ticket GLPI |
| CMDB | ACME | assets, environnement, liens applicatifs, criticité Payments et blast radius |
| TICKET | cas antérieurs | symptômes, RCA approuvées, actions, preuves de validation, faux positifs, rollback |
| POLICY | sécurité | approbation HITL, séparation simulation/LIVE, zones interdites |

**Ne pas inventer des OID officiels ni des commandes spécifiques garanties** : les fiches détaillées doivent être liées aux documents éditeur officiels avec version/URL/date/licence. Les log samples fournis en démonstration seront marqués `SYNTHETIC`.

## Schéma documentaire normatif `rag-ops-doc-v1`
```json
{
  "doc_id":"SYN-FOS-FC-PORT-001",
  "kind":"EVENT_CATALOG",
  "vendor":"Broadcom/Brocade",
  "product":"Fabric OS",
  "version_scope":"SIMULATION_ONLY",
  "title":"Fictional port link degradation",
  "language":"fr",
  "source_type":"SYNTHETIC",
  "license":"INTERNAL_DEMO",
  "asset_types":["FC_SWITCH","HBA","STORAGE_PORT"],
  "signal":{"transport":"SYSLOG","event_key":"DEMO_FC_PORT_DEGRADED","sample":"DEMO: fc port 8/16 high CRC rate"},
  "runbook":{"triage":["Check port counters in synthetic simulator","Cross-check CMDB affected paths"],"remediation_mode":"SIMULATED_ONLY"},
  "relationships":{"service":"ACME Payments","dependent_assets":["brocade-fc01"]},
  "confidence_scope":"illustrative; not a vendor-authenticated event",
  "ingest":{"chunk_sha256":"COMPUTE_ON_IMPORT","embedding_model":"RECORD_REAL_VERSION","indexed_at":"RECORD_ACTUAL_TIME"}
}
```

## Pipeline à construire sans casser l'existant
1. **Acquisition contrôlée** : récupérer index RAG existant et documents originaux ; rejeter secrets, données client, captures sensibles, licences non redistribuables.
2. **Parser typé** JSONL + documents autorisés, UTF-8, limite de taille, validation stricte, version de schéma, déduplication SHA-256, origine `SYNTHETIC` / `VENDOR_OFFICIAL` / `INTERNAL_APPROVED`.
3. **Normalisation** : fabricant, produit/version, équipement, événement, OID/varbind ou log signature, sévérité **calculée par règle versionnée**, contexte CMDB et run_id.
4. **Indexation** : découpage structuré préservant l'ID et les métadonnées, embeddings versionnés, recherche hybride (mot clé + vectorielle), filtres fabricant/version/source.
5. **Qualité** : golden questions SAN P1 Payments, FC CRC, multipath APD/PDL, SRDF lag et capacity ; exiger citations `doc_id, version, page/section, evidence_id`. Un document simulé ne doit jamais devenir une vérité constructeur.
6. **Analyst/Critic** : l'analyste doit signaler les limites et un niveau de confiance, le critic rejette toute remédiation dangereuse/non sourcée et déclenche HITL ; production LIVE désactivée.
7. **Demo Director** : au cue `enrich`, exposer les sources réellement retrouvées ; au cue `analyze`, justifier diagnostic et impact ; au cue `verify`, afficher mesures de rétablissement avec provenance.

## Plan de qualification
- Comptages par fabricant/type/version, couverture et taux de duplicats ;
- Recall@k sur requêtes de référence et précision des citations ;
- Test de documents contradictoires, OID inconnu, mauvaise version, signaux bruités et injection de prompt dans un faux syslog ;
- Évaluation des risques de données sensibles et de hallucinations ;
- Tests isolés, puis intégration avec le portail NOC **sans écrire dans les équipements ni dans la production**.

## Première étape exécutable
Voir `demo/rag_ops_fixture_catalog.json` pour des scénarios **synthétiques**, consultables hors ligne : ils servent de fixtures pour les futurs tests de recherche et de chorégraphie, pas comme documentation vérifiée des fabricants.
