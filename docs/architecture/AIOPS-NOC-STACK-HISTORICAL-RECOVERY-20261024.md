# AIOps — Capitalisation de la stack NOC et observabilité (24 octobre 2026)

**Auteur : Abdelhalim Talbi.** **Statut : reconstruction documentaire sourcée — pas une constatation de runtime en octobre 24.** Ce document prime sur les hypothèses de reconstruction ; conserver les sources originales et ne pas écraser les services.

## Sources historiques concrètes
- Conversation/diagnostic du 16 octobre : `Texte collé(20261016-162216).txt` (docker inspect, ~162 kB) : conteneurs `aiops_noc_thruk` et `aiops_noc_checkmk` **running** à ce moment-là, projet Compose `aiops_noc`, répertoire `/home/aiops/aiops-v1/stack/noc`, réseau `aiops_noc_default`.
- Même inventaire : Thruk image `aiops_noc-thruk`, port hôte **8120→80** ; Checkmk `checkmk/check-mk-community:2.5.0-latest`, **8119→5000** et Livestatus **127.0.0.1:6557**. *Attention : les images étiquetées latest dérivent ; versions et ports historiques ne prouvent pas l'état présent.*
- `Texte collé(20261019-182232).txt` : conteneurs NOC toujours signalés `running` le 19 octobre ; `/home/aiops/aiops-v1/stack/noc/compose.yaml`, volumes Checkmk `stack/noc/checkmk:/omd/sites` et Thruk `stack/noc/thruk:/etc/thruk`.
- `Texte collé(20261019-173734).txt` : inventaire des volumes V1 notamment Grafana provisioning/dashboards, n8n workflows, GLPI CMDB, policy YAML, Alloy et observabilité.
- Décision utilisateur du 16/17 octobre : **véritable NOC Checkmk + Thruk**, multi-environnements/clients, états OK/WARN/CRIT/UNKNOWN, acquittements, downtimes, topologie, services métiers ; fédération Prometheus, Alertmanager, Loki, Grafana, GLPI, n8n dans le portail AIOps.
- Trajectoire historique V11 / V25 : Prometheus/Grafana/Checkmk/Thruk avaient une surface HTTP rapportée disponible ; Loki/Alertmanager n'étaient pas accessibles depuis localhost lors d'un test ; V25 observait que « HTTP up » ne valide **pas** les données métier. Ces résultats sont datés, à reconfirmer.

## Architecture de référence (cible, non déploiement)
```text
Événements simulés (sources déterministes, run_id / incident_id)
  | SNMP traps / syslog / agents / logs / métriques
  v
Normalisation + horodatage + asset_id + CMDB/dépendances
  |----> Checkmk (hosts/services, états, acknowledgements/downtime)
  |----> Thruk (multi-backend, views NOC, panorama; backend Livestatus requis)
  |----> Prometheus / Alertmanager / Loki / Grafana (métriques/alertes/logs)
  |----> n8n orchestration → Analyst + Critic + RAG → Policy/HITL simulation
  |----> GLPI (ticket, lien service/CI, statut ; écriture seulement en environnement autorisé)
  `----> Evidence ledger (run_id, event_id, source_time, observed_at, SHA256)
                |
                v
       Portail unique :17777 / NOC Command Center / DEMO Timeline
```
Ne pas supposer que Thruk est un backend de supervision : son rôle est interface multi-backend Livestatus (voir documentation officielle). Checkmk possède son propre moteur de surveillance. Le NOC unifié est une **vue de consolidation** et non une duplication arbitraire des systèmes sources.

## Écrans NOC à restaurer
1. **Wallboard opérationnel** : scope DC/client, fenêtre temporelle, état hôtes/services, alertes, ack/downtime, santé des collecteurs, données vieillissantes (stale) clairement indiquées.
2. **Topologie métier** : Brocade/Cisco SAN → stockage Pure/PowerMax → ESXi / multipath → application ACME Payments ; impacts et dépendances CMDB explicitement simulés ou prouvés.
3. **Incident drill-down** : alerte source, symptômes, logs et trap liés, classification Analyst/Critic, confiance, ticket GLPI, vérification et décision HITL.
4. **Demo Director** : les neuf cues `detect/correlate/enrich/analyze/ticket/approve/simulate/verify/close`, avec capture Grafana/n8n/GLPI à l'étape exacte, identité de run et provenance.
5. **RAG evidence viewer** : extrait documenté avec constructeur/version/protocole/message, source et limites ; séparer contenu corpus simulé des manuels éditeurs officiellement téléchargés.

## Règles de vérité et de sécurité
- Un statut Docker running, un HTTP 200, une page Grafana login ou un PNG dont le SHA correspond ne prouve pas l'état réel d'un incident.
- Les captures de fixtures GitHub Actions restent `SYNTHETIC_LOCAL_FIXTURE` ; sans session métier vérifiée, aucun statut `runtime_authenticated=true`.
- L'enrichissement et les simulations portent une identité cohérente `run_id/event_id/asset_id/execution_id/ticket_id` et un temps source distinct du temps de capture.
- Aucun redémarrage, changement de port, mise à jour automatique de `latest`, import GLPI, SNMP trap réseau réel, ni remédiation LIVE dans la production Debian sans approbation explicite.
- Travailler en branche de PR #36 puis tester un Compose isolé avec volumes/ports dédiés **avant** toute proposition de migration. Garder un inventaire READ_ONLY des services/volumes sous `/home/aiops`.

## Ordre de reprise à forte valeur
P0 : récupérer `stack/noc/compose.yaml`, configuration Checkmk et Thruk, dashboards provisionnés, workflows n8n, échantillons de preuves ; vérifier le contenu et les secrets **localement**. P1 : construire un dataset synthétique cohérent et un adaptateur de lecture seulement (pas d'API PROD écrite), puis tester snapshots checkpoint à checkpoint. P2 : bibliothèque RAG de procédures et taxonomie SNMP/syslog, évaluation des citations et garde-fous fabricant ; P3 : industrialiser CI/packaging/documentation, qualification navigateur et restitution sur `:17777`.

## Documents adjacents
- `docs/recovery/OCTOBER-2026-ARCHIVE-CONTEXT-AND-REUSE.md` : ZIPs et scripts reconnus ;
- `docs/demo/STAR-NINE-SCENE-CHROMIUM-QUALIFICATION.md` : test sur fixtures, pas sur applis ;
- `docs/PROJECT-CONTINUITY.md` : continuité générale.
