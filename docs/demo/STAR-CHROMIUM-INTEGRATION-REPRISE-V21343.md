# AIOps 2.0 — STAR V2.13.43 — reprise Chromium lecture seule (2026-10-23)

## Portée de cette livraison
Intégration dans la branche de PR draft #36 du candidat précédemment qualifié hors ligne :
- `demo/star_snapshot_browser.py` (SHA Git blob `a81ed0de6160dae553ead385480e9d7fc835abd4`).
- `tests/test_star_snapshot_browser.py` et `tests/test_star_snapshot_browser_hardening.py`.
- `.github/workflows/star-browser-readonly-offline.yml`.
- `docs/demo/STAR-BROWSER-READONLY-HLD-LLD-V21339.md`.

**Aucune capture des applications Debian réelles n'a été effectuée.** Le statut `CAPTURED_UNREVIEWED` et un SHA-256 ne certifient ni origine runtime, ni anonymisation complète, ni décision HITL, ni succès métier.

## HLD — frontière de confiance
Identité canonique issue de l'ingress → plan de capture à URL/ID exacts → autorisation opérateur séparée → Chromium isolé → contrôle GET fail-closed → DOM (run_id, correlation_id, event_ref, état) → masques de confidentialité → PNG + manifeste → `star_browser_manifest_gate` → revue humaine.

Le portail utilisateur reste unique sur `:17777`. Les pages externes doivent être des vues *de l'événement exact*, pas des dashboards génériques : n8n (execution ID), Grafana (UID + fenêtre absolue et run_id), GLPI V1 `:8080` (ticket ID). GLPI `:18080` est explicitement exclu.

## LLD — conditions de refus
- Dry-run par défaut ; `--capture` ne suffit pas pour l'opérateur : `AIOPS_STAR_ALLOW_OPERATOR_READ=1` requis. `AIOPS_STAR_NO_RUNTIME=1` interdit la navigation runtime, y compris si l'opt-in est défini.
- Navigation GET exacte seulement ; sous-ressources GET explicitement revues et listées ; POST, WebSocket, popup, téléchargement, redirection, requête externe et erreur JavaScript font échouer la capture.
- Aucune identité manquante/contradictoire n'est fabriquée ; sélecteurs DOM exacts ; masques obligatoires, mais leur présence ne garantit pas l'absence de données sensibles ailleurs.
- Manifeste sans URL brute : gabarit expurgé ; horodatage UTC ; SHA-256 ; provenance `ISOLATED_TEST_FIXTURE` ou `OPERATOR_BROWSER_UNREVIEWED`. `event_time_alignment` reste non vérifié sans horodatage externe.
- Sorties atomiques exclusives, permissions 0600, refus d'écrasement. Pas d'import, d'appel mutateur, de modification CMDB/tickets ou de remédiation LIVE.

## Qualification et limites
Commande locale réellement exécutée sur le candidat cumulatif :
```sh
AIOPS_STAR_NO_RUNTIME=1 python3 -m unittest discover -s tests -p 'test_star_*.py' -q
```
Résultat : **326 tests PASS**, dont **25 tests Chromium isolés** (fixture HTML synthétique, navigateur Chromium local). Ce n'est **pas** une qualification complète du dépôt GitHub ni un essai sur la production.

La CI `STAR Chromium read-only fixture qualification` vérifie la branche de PR avec `AIOPS_STAR_NO_RUNTIME=1`. Son statut doit être lu sur le SHA GitHub correspondant, sans extrapoler à une validation métier.

## Reprise, promotion et rollback
1. Examiner les CI du dernier SHA ; ne pas fusionner automatiquement.
2. Qualifier les deep links réels **sans capture** puis, après autorisation opérateur explicite, procéder en lecture seule avec revue des requêtes GET autorisées et des masques.
3. Comparer chaque PNG/manifeste à l'identité d'ingress indépendante et à l'événement horodaté ; séparer succès technique n8n, HITL, Policy et résultat métier.
4. Continuer le diagnostic `RUN_ID_MISSING` du flux V1 02 Webhook→RAG→Canonical Identity→Call Analyst→03 Prepare Analyst Payload sur traces expurgées ; ne jamais corriger par génération d'identité aval.
5. Pour rollback : revert des commits V2.13.43 sur la seule branche de PR. Aucune opération sur les services Debian, le bridge V1, la CMDB, les tickets ou `main`.

**Aucun secret ni capture runtime n'est destiné à GitHub.** Les captures réelles doivent rester dans un coffre de preuves privé avec contrôle d'accès et durée de conservation.
