# ACME P1 — corrélation NOC signé → Core Run (lecture seule)

Ce lot réutilise le scénario SAN → hôte → VM → Payments de la PR #50 (portage ciblé de la PR #36), ainsi que le vérificateur HMAC NOC existant de `app/portal/noc_runtime.py`. Aucune copie massive de la PR #36.

## Route

`GET /api/portal/acme-correlation` exige `Authorization: Bearer <AIOPS_PORTAL_READ_TOKEN>`. Elle charge le scénario synthétique validé, lit un NOC via l'adaptateur signé HMAC existant, puis lit `GET /api/runs/{run_id}` sur le Core interne configuré. Aucune écriture, création de ticket, action de remédiation ou lecture du serveur Debian.

Le résultat `CORRELATED_UNVERIFIED` exige : HMAC du read model validé, source NOC avec indicateurs de sécurité explicitement faux, digest de source, même identifiant Run entre NOC et Core, incident `INC-ACME-DEMO-SAN-001` dans les deux sources, mode `DEMO`, version Core valide. Sinon `UNKNOWN`. Une source NOC absente, une erreur réseau, une discordance, un mode LIVE ou un Core inaccessible ne produit jamais PASS.

`glpi_ticket_claim` est une **simple affirmation de l'amont signé** ; `ticket_id=null` reste invariable, car aucun appel à l'API GLPI n'est effectué. Un HMAC de read model prouve uniquement l'origine de la charge signée, pas la réalité du ticket ni une capture d'écran. `runtime_attested=false`, `production_qualified=false`, `live_remediation_authorized=false` dans tous les cas. L'endpoint est protégé par un jeton opérateur ; ne pas afficher ce contenu dans une page publique sans RBAC.

## Qualification

Tests unitaires hors ligne `tests/test_acme_itsm_correlation.py` : corrélation positive non qualifiée, refus LIVE, mismatch Run/Incident, HMAC absent/faux, version invalide, ticket synthétique, authentification obligatoire, absence NOC et montage dans le portail. Workflow `.github/workflows/quality.yml` réutilisé. Ces tests remplacent les upstreams par des doubles contrôlés : **pas de qualification d'intégration réelle NOC/Core/GLPI**.

## Suite

Ajouter un vrai adaptateur GLPI en lecture seule avec authentification et identifiant de ticket confirmé côté GLPI, preuve de fraîcheur, correspondance des IDs et isolation des tenants. Ajouter un test d'intégration avec un vrai GLPI éphémère en CI, puis une vue opérateur authentifiée. Aucun ticket réel n'est revendiqué.
