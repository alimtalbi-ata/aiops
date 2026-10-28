# ACME NOC Trace v1 — contrat NOC / observabilité / Copilot

Date : 2026-10-28. Dépendance : contrat canonique scénario de la PR #133 ; branche de développement empilée, pas de fusion indépendante avant sa base.

Le portail unique expose « Lire trace ACME NOC » dans son panneau NOC et GET /api/noc/acme-trace. Authentification Bearer AIOPS_PORTAL_READ_TOKEN obligatoire avant lecture du fixture. Contrat additif aiops.acme-noc-trace.v1 ; 401 sans autorisation, 503 si fixture, source RAG ou contrat invalides ; no-store. Aucun changement du contrat aiops.acme-scenario.v1.

Le read model consomme build_acme_scenario_contract de #133 : événements SIM-EVT-ACME-001..009, incidents ACME-DEMO-SAN-001 / ACME-DEMO-PAY-002, chemin SAN-FABRIC-A → HOST-ESX-01 → VM-PAY-01 → APP-PAY-01 et Run SIM-ACME-* (libellé fictif, pas un Run Core). Le temps virtuel reprend l'ancrage existant simulation_checkpoint_timestamp_utc=2026-10-25T09:00:00Z, avec cadence illustrative de 60 s par checkpoint, 09:00..09:08 UTC. Provenance PRESENTATION_ONLY_NOT_RUNTIME_EVENT ; tous les event_timestamp_utc restent null et les statuts MISSING. Aucun événement runtime n'est daté par cette projection.

Deux slots de métriques visibles : SAN FC CRC delta et Payments p95. value=null, state=NOT_OBSERVED, source=GRAFANA_NOT_QUERIED. Aucun chiffre inventé ni appel Grafana. L'adaptateur existant /api/noc/grafana-health prouve uniquement la santé HTTP, pas les métriques.

RAG : réemploi du catalogue synthétique PR #36 déjà porté sur main, via build_demo_rag, sur l'hôte exact esx-acme-01 issu du CI HOST-ESX-01. Citation doc_id et SHA-256 ; aucune inférence LLM ni preuve de causalité. Sans correspondance : UNKNOWN_NO_EXACT_SOURCE, citations vides ; source absente/corrompue : HTTP 503, sans fallback. Claims tenant/org/workspace/account refusés. Le viewer n'est pas une ACL multitenant.

Tests contractuels HTTP ASGI, sécurité et régression dans quality.yml existant. NOT_TESTED : métriques Grafana observées, Checkmk/Thruk, Core/GLPI/Temporal sur ce parcours, ACL tenant runtime, navigateur réel, Ollama, captures et vidéo. Aucun accès NGX, Debian, déploiement ou effet LIVE.

Coordination : Explore/Story, données ACME et ITSM doivent conserver les IDs et le SHA du scénario #133. Prochain micro-lot : lecture Grafana métriques avec datasource, provenance et identité tenant qualifiées avant corrélation runtime.
