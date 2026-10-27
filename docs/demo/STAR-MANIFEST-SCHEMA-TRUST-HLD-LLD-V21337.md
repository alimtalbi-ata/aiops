# ACME STAR V2.13.37 — contrôle strict des manifestes Chromium (2026-10-23)

## État réel de l'intégration

Ce correctif est limité au **validateur hors ligne** `demo/star_browser_manifest_gate.py` et à ses tests. L'adaptateur de capture Chromium `demo/star_snapshot_browser.py` reste **candidat local, non intégré à la PR**. Aucune capture runtime n'est revendiquée.

## HLD — frontières de confiance

Entrée canonique indépendante (run_id, correlation_id, event_ref) → manifeste non fiable → vérification des champs autorisés et du chemin d'origine expurgé → contrôle d'identité → validation du PNG/CRC/SHA-256 → timeline STAR → revue humaine. Une intégrité vérifiée n'est ni une authentification de la page ni une approbation HITL. Un succès technique n8n ne démontre pas une clôture métier.

## LLD — nouvelles invariantes

- Refuser toute clé de manifeste hors schéma autorisé, y compris les attributs d'autorité inconnus ou les champs secrets.
- Accepter `source_url_redacted` uniquement sous trois formes statiques : GLPI V1 ticket, n8n execution et Grafana dashboard ; refuser les URL brutes, paramètres, hôtes et chemins arbitraires.
- Si `event_time_alignment` existe, seule la valeur `UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP` est autorisée. La concordance temporelle doit être vérifiée par une source événementielle indépendante.
- Conserver `runtime_authenticated=False`, `business_validated=False`, `human_approval_authenticated=False` et `live_action_authorized=False`.
- Refuser identités manquantes ou contradictoires ; aucune création d'identifiant dans un composant aval.

## Qualification et rollback

Commande isolée : `python -m unittest discover -s tests -p 'test_star_browser_manifest_gate.py' -v`. Les fixtures sont synthétiques. La CI GitHub doit être examinée sur le SHA exact après publication. Revert des commits de cette branche seulement en cas de régression ; **ne pas modifier main, les services Debian, les ports ou le bridge V1**.

## Points ouverts

- Intégrer l'adaptateur Chromium lecture seule depuis le candidat offline après revue et test E2E isolé.
- Capturer uniquement des pages autorisées et réellement présentes (portail :17777, GLPI V1 :8080, n8n, Grafana) ; journaliser IDs, timestamps, URL expurgées, SHA-256, état attendu/observé.
- Diagnostiquer `RUN_ID_MISSING` dans workflow 02 → 03 avec exports expurgés. Ne jamais corriger en fabriquant un run_id.
- Quality Gates : `runtime-e2e` reste bloqué après la création du run synthétique ; analyser le rapport Temporal/worker isolé avant toute modification du pipeline.
