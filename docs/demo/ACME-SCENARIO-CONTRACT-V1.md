# ACME — contrat canonique scénario / événements v1

Date : 2026-10-28. **Propriétaire : lot données/fixtures ACME.** Source de vérité : `app/portal/acme-fixtures.json` et `app/portal/acme_fixture_contract.py`. Le schéma d'entrée `aiops.acme.demo.v1` reste inchangé (six CI, deux incidents). Le nouveau schéma de projection `aiops.acme-scenario.v1` est **additif**, distinct du schéma du fixture.

## Lecture et consommation

- `GET /api/demo/acme-scenario` avec `Authorization: Bearer <AIOPS_PORTAL_READ_TOKEN>` ; refus 401 si absent/incorrect, 503 si configuration manquante ou fixture/projection invalide. Aucune lecture du fixture avant authentification.
- `POST /api/demo/explore-story/control` conserve `aiops.acme-explore-story.v1`, les actions et les champs existants. Explore et Story projettent désormais leurs neuf checkpoints depuis le même contrat `build_acme_scenario_contract`, sans source d'événements parallèle.
- `source_sha256` ancre les **octets exacts** du fixture ; `SIM-ACME-<16 premiers hex majuscules>` est un libellé de scénario, jamais un Run Core. Les événements `SIM-EVT-ACME-001` à `009` sont des identifiants stables de checkpoints **non observés**. L'ID `SIM-GLPI-<12 hex>` est un libellé fictif, jamais un ticket GLPI.
- Les deux incidents `ACME-DEMO-SAN-001` (P1) et `ACME-DEMO-PAY-002` (P2) sont liés à chaque événement. Le chemin est `SAN-FABRIC-A → HOST-ESX-01 → VM-PAY-01 → APP-PAY-01`. La fabric B reste une dépendance déclarée du fixture, sans basculement prouvé.
- Les champs `runtime_attested`, `production_qualified`, `live_remediation_authorized`, `backend_writes` sont toujours `false`. `ticket_id` et `event_timestamp_utc` restent `null`. Aucun tenant réel, accès GLPI, exécution Temporal, ni preuve LIVE n'est inféré.

## Exemple JSON (extrait illustratif, pas une capture runtime)

```json
{
  "schema": "aiops.acme-scenario.v1",
  "fixture_schema": "aiops.acme.demo.v1",
  "organization": "ACME-DEMO",
  "mode": "DEMO",
  "state": "SIMULATED_UNVERIFIED",
  "provenance": "SIMULATED_TARGET",
  "source_sha256": "<SHA256_HEX_DU_FIXTURE>",
  "scenario": {
    "run_id": "SIM-ACME-<PREFIXE_SHA256>",
    "run_id_provenance": "DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN",
    "incident_id": "ACME-DEMO-SAN-001",
    "impact_incident_id": "ACME-DEMO-PAY-002",
    "impact_path": ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"],
    "ticket_id": null,
    "event_timestamp_utc": null,
    "simulation_ticket_id": "SIM-GLPI-<PREFIXE_SHA256>",
    "simulation_ticket_provenance": "SYNTHETIC_LABEL_NOT_A_GLPI_TICKET"
  },
  "events": [
    {
      "id": "SIM-EVT-ACME-001",
      "sequence": 1,
      "cue": "detect",
      "service": "grafana",
      "view": "alert_dashboard",
      "incident_id": "ACME-DEMO-SAN-001",
      "impact_incident_id": "ACME-DEMO-PAY-002",
      "status": "MISSING",
      "event_timestamp_utc": null,
      "provenance": "SIMULATED_TARGET"
    }
  ],
  "event_count": 9,
  "runtime_attested": false,
  "production_qualified": false,
  "live_remediation_authorized": false,
  "backend_writes": false
}
```

L'extrait ne contient qu'un événement sur neuf ; les valeurs entre chevrons sont des placeholders documentaires, pas des valeurs d'API. Pour obtenir un document complet, utiliser le GET authentifié sur un portail de test local.

## Contrat de coordination

Les lots portail, Story, NOC et ITSM doivent **consommer** ce GET ou `build_acme_scenario_contract` ; ne pas recalculer des IDs de Run, événement ou ticket depuis une autre source. Le read model entreprise de [PR #127](https://github.com/alimtalbi-ata/aiops/pull/127) est une extension de démonstration 60 CI distincte : ses `SIM-EVT-001` et `SIM-GLPI-001` ne sont pas des IDs de ce scénario minimal et ne doivent pas être présentés comme une corrélation Core/GLPI. Une future convergence devra mapper explicitement les deux projections par `source_sha256` et IDs d'incident, avec tests, sans changement silencieux de schéma.

Le jeton viewer est une barrière de lecture du fixture public synthétique, **pas** une ACL tenant qualifiée. Aucune promotion de cette API vers des observations tenant/LIVE sans identité serveur, contrôle RBAC et preuves indépendantes.

Tests : `tests/test_acme_scenario_contract.py` et `tests/test_portal_explore_story.py` via `.github/workflows/quality.yml`. Les tests utilisent des requêtes ASGI in-process et ne qualifient pas de navigateur réel ni de service GLPI/Core/Temporal.
