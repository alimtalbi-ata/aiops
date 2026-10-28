# ACME — Timeline Evidence et bilan métier (P1, contrat synthétique)

Cette page réutilise le **graphe ACME validé sur `main`** (`app/portal/acme_impact_read_model.py`) sans reprendre en masse la PR #36. Elle expose `/demo/acme-evidence-timeline` et `/api/demo/acme-evidence-timeline` depuis le portail canonique, en lecture seule. Ne pas confondre avec le Run Core/Temporal ou le ticket GLPI.

## Contrat vérifiable

Les neuf checkpoints (détection, corrélation, enrichissement, analyse, ticket, approbation, simulation, vérification, clôture) conservent `MISSING`, timestamp et hash absents, `runtime_authenticated=false`. Les identifiants `SIM-ACME-...` et `SIM-GLPI-...` sont dérivés du fixture SHA-256 ; `ticket_id` réel reste `null`. Toute tentative de promouvoir un champ LIVE, une capture non attestée, un horodatage inventé ou un graphe incohérent est refusée.

Le bilan métier **ne mesure pas** les indisponibilités, transactions ou pertes financières. Il présente uniquement le chemin de dépendance et le nombre de CI du fixture. L'état opérationnel est `UNKNOWN` et la vidéo finale `BLOCKED_NO_AUTHENTICATED_CAPTURES`. La vue HTML ne fait aucun appel externe, n'embarque pas de JavaScript, ne contient pas de secrets et applique les en-têtes `no-store`/CSP existants.

## Storyboard client conditionnel — 11 minutes, pas une vidéo produite

| Minute | Contenu prévu | Critère préalable |
|---|---|---|
| 0:00–1:00 | Contexte ACME, distinction DEMO / LIVE | Page du portail accessible |
| 1:00–2:15 | Détection SAN P1 et preuve Grafana/Thruk | Capture opérateur authentifiée |
| 2:15–3:30 | Corrélation NOC et ID Run canonique | Core et identifiants vérifiés |
| 3:30–4:45 | Graphe SAN → hôte → VM → Payments P2 | Topologie validée, provenance affichée |
| 4:45–6:00 | Enrichissement et analyse sourcée | Sources RAG qualifiées et Critic |
| 6:00–7:15 | Ticket GLPI et trace n8n | IDs liés à la même session |
| 7:15–8:30 | Approbation HITL et refus LIVE | RBAC et politique fail-closed |
| 8:30–9:45 | Simulation, vérification, limites | Preuves datées non falsifiées |
| 9:45–11:00 | Bilan métier et suite opérationnelle | Disponibilité/impact mesurés ou UNKNOWN |

**Gate de production vidéo :** tant que les captures Playwright de portail, Thruk, Grafana, n8n et GLPI ne sont pas réellement obtenues par des sessions autorisées, revues pour confidentialité, reliées par `run_id`/`incident_id`/`ticket_id` et contrôlées par Evidence Studio (chaîne PR #43 → #121), **ne pas générer de vidéo client**. Les tests de fixtures et un montage FFmpeg technique ne remplacent pas ces preuves.

## Qualification

`python -m unittest discover -s tests -p 'test_acme_evidence_timeline.py' -v` dans `.github/workflows/quality.yml`. Test contractuel hors ligne uniquement ; pas de Playwright réel, GLPI, Thruk, n8n, runtime Core ni capture LIVE qualifiés par ce lot. La recette E2E avec services éphémères est un chantier distinct à réaliser sans mocks d'intégration.
