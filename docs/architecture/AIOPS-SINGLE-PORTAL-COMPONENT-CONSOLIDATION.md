# AIOps — Plan de convergence des composants vers un portail unique

## Principe de déploiement

Point d'entrée public cible unique : **http://10.79.94.202:17777/**. Ne pas exposer les ports internes GLPI, n8n, Grafana, Checkmk, Thruk, Temporal ou services DGX directement au poste client. Les liens devront passer par des routes vérifiées du portail avec SSO, autorisation et proxy/gateway maîtrisé ; l'inventaire des liens est **un plan de routes**, pas la preuve qu'elles sont montées.

## Inventaire consolidé de 20 familles

`app/portal/platform_registry.py` est maintenant la source canonique des 20 familles (NOC, Checkmk, Thruk, Grafana, Prometheus, Alertmanager, GLPI, n8n, Core, Temporal, Worker, DGX Analyst/Critic, Policy/HITL, Evidence, RAG, Digital Twin, Simulator, Copilot, Mattermost et PagerDuty). `demo/noc_platform_registry.py` reste un shim de compatibilité. `GET /api/platform/components` est monté dans le code source de `portal.main:app` et renvoie uniquement le plan statique ; cela ne constitue pas une connexion aux composants.

Chaque composant est `UNKNOWN` par défaut. Seule une observation fraîche (≤ 300 s), horodatée en UTC et authentifiée peut lui donner un autre état. **Les chemins prévus sont actuellement tous marqués `available_in_portal=false` et `requires_route_integration=true`**, même si un état observé est bon. Aucun iframe ou redirection vers un port interne ne doit être ajouté automatiquement.

## Rattachement métier cible

| Domaine | Composants | Référence d'état et responsabilités |
|---|---|---|
| Pilotage | Portail :17777, NOC, Checkmk, Thruk | Vue opérateur / hôtes / services / incidents ; Checkmk/Thruk restent sources de supervision, jamais Core Run |
| Cycle de vie | Core, Temporal, Worker | Identité canonique Incident/Run, orchestration durable, traces des activités |
| Intelligence | DGX Analyst/Critic, RAG, Digital Twin | Diagnostics sourcés, enrichissement, impacts et dépendances |
| Décision et sécurité | Policy, HITL, Simulator | Autorisations déterministes, validation humaine, replay explicitement SIMULATION |
| ITSM et intégrations | GLPI, n8n, Mattermost, PagerDuty | Tickets, CMDB, notifications et escalades ; ne remplacent jamais l'état Core |
| Observabilité | Prometheus, Grafana, Alertmanager | Métriques, états des services, alertes et chronologie |
| Preuves et assistance | Evidence Center, Copilot | Hash, provenance, vérification, recherche et diagnostic |

**Nom à confirmer :** « checkmate » cité dans la demande peut désigner Checkmk, un produit distinct ou un composant interne. Le dépôt historique confirme Checkmk/Thruk ; ne pas faire passer « checkmate » pour une intégration identifiée sans audit.

## Démarche de convergence

1. **Inventaire réel en lecture seule :** inspecter le conteneur qui sert :17777, ses routes, identité, dépendances, réseaux Docker et composants actifs ; comparer au registre de 20 familles.
2. **Architecture des routes :** confirmer l'application FastAPI/ASGI ou le reverse proxy réellement déployé, puis fixer pour chaque service un contrat d'accès central, sans ouvrir de port supplémentaire. Ne pas exposer de credentials, interfaces d'administration ni protections fragiles derrière un simple iframe.
3. **Contrats de données :** Core demeure source du Run ; Checkmk/Thruk fournissent hôtes/services ; GLPI pour CI/ticket ; n8n pour flux ; Temporal pour workflow ; Grafana/Prometheus pour mesures. Garantir les `run_id`, `incident_id`, source, timestamp et états `UNKNOWN` en cas de panne.
4. **Démo automatisée :** replay explicitement synthétique dans le vrai chemin d'ingestion AIOps de l'environnement d'intégration, puis lecture de ses étapes et preuves effectivement produites. La démo ne doit ni créer des succès fictifs ni toucher à la remédiation LIVE.
5. **Recette :** auth/SSO, navigation, statuts réels/absents, flux corrélés, rejets policy/HITL, redémarrage des services et rollback ; captures navigateur de la vraie interface quand elle est intégrée.
6. **Bascule :** snapshot, approbation, route vérifiée, monitoring et rollback prouvé avant de modifier le portail Debian de production.

## État de ce commit

**Livré dans le code de la branche :** `GET /api/platform/components` est enregistré une seule fois dans l'application FastAPI existante et expose 20 entrées `UNKNOWN`, `route_mounted=false`, `runtime_authenticated=false`, sans fournisseur de santé ni appel réseau. **Non livré / non attesté :** `/noc`, `/api/noc/state`, les routes graphiques des composants, SSO/authentification runtime, connexions réelles, automatisation E2E et déploiement Debian. Aucun état « OK » n'est inventé.

La présence historique de Checkmk Community 2.5 et Thruk au sein de l'ancienne stack est une piste d'intégration ; ses ports et conteneurs doivent être revérifiés sur la machine avant tout rattachement.

## Endpoint de registre statique (25 octobre 2026)

Le module `app/portal/platform_registry_router.py` ajoute uniquement `GET /api/platform/components` via `app.include_router(...)` dans `app/portal/main.py`. Il réutilise l'application existante : aucun serveur, listener, port, proxy, tâche ou accès fournisseur n'est lancé. La réponse indique `source_mode=STATIC_REGISTRY_PLAN`, `component_observation_source=ABSENT`, `route_mount_attested=false`, `runtime_e2e_qualified=false` et `production_qualified=false`. Chaque ligne demeure `UNKNOWN`, sans timestamp ni attestation. Les valeurs en query string ne peuvent pas promouvoir un composant.

La route est testée avec un client ASGI isolé. Cela prouve le montage dans le code importé en CI, pas le déploiement du même artefact ni l'authentification de la machine cible. `/noc` et `/api/noc/state` utilisent un adaptateur distinct dans `demo/noc_portal_integration.py` et restent non montés dans l'application de production connue ; le read model réel n'est pas fourni.
