# ACME STAR V2.13.35 — Identité des captures, HLD/LLD et reprise

**Statut : contrat Python et tests publiés sur branche de PR draft ; navigateur Chromium renforcé dans candidat offline local. Aucune capture runtime, validation métier ou autorisation LIVE revendiquée.**

## HLD — séparation des responsabilités

Portail unique `:17777` (aucune modification) → scénario ACME Brocade SAN P1 / Payments P2 → identité canonique à l'entrée de 02 → événements n8n/Grafana/GLPI V1 → plan de capture **lecture seule** → comparaison stricte de l'identité de la page → capture PNG masquée → manifeste SHA-256 `CAPTURED_UNREVIEWED` → revue humaine. Le contrat publié `demo/star_capture_identity_guard.py` n'effectue aucune requête et ne produit aucun identifiant.

Les trois clés `run_id`, `correlation_id` et `event_ref` doivent être présentes **des deux côtés** : valeurs attendues provenant de l'ingress canonique, valeurs observées lues séparément dans le DOM de la page de l'événement. Aucune valeur absente ne peut être substituée à partir de l'autre côté. Le contrôle exact ne prouve pas la provenance de la page.

## LLD — refus explicites

- Identité attendue ou observée absente, malformée, de type non chaîne, tronquée ou contradictoire → `ValueError`, sans récupération silencieuse.
- Succès du contrôle → `identity_consistent=True` uniquement. `runtime_authenticated`, `business_validated`, `human_approval_authenticated` et `live_action_authorized` restent `False`.
- Dans le **candidat local Chromium V2.13.35**, le DOM `correlation_selector` est désormais obligatoire et comparé strictement ; `run_id` et `event_ref` sont contrôlés par le même gate. Les URLs persistées sont réduites à un gabarit de route, sans nom d'hôte, slug ni ID brut. Ce candidat navigateur **n'est pas encore synchronisé** sur GitHub.
- Aucun import ni action de remédiation. Simulation strictement isolée, dry-run par défaut, refus si origine/événement/état non concordants. La validation d'une capture de ticket GLPI V1 requiert la bonne instance sur `:8080`, pas `:18080`.
- L'intégrité SHA-256/PNG n'est pas une authentification runtime ; une capture n8n `success` n'est pas une validation métier.

## Continuité V1 02 → 03

Chaîne à inspecter sur exports expurgés : **Webhook 02 → RAG → Canonical Identity → Call Analyst → Prepare Analyst Payload 03**. Pour `RUN_ID_MISSING`, rechercher le premier nœud où `run_id` est absent ou contredit, puis corriger à cette frontière uniquement après qualification isolée. Ne pas fabriquer de valeur dans 03 et ne pas redémarrer le bridge V1 containerd incomplet. Ne toucher ni à la CMDB ni aux tickets sans validation humaine.

## Qualification et rollback

Tests autonomes : `python3 -m unittest discover -s tests -p 'test_star_capture_identity_guard.py' -v`. Candidat Chromium local : `AIOPS_STAR_NO_RUNTIME=1 python3 -m unittest discover -s tests -p 'test_star_*.py' -q`. Les tests de navigateur utilisent du HTML synthétique, pas les applications Debian.

La publication est confinée à la branche `feat/v21310-star-portal-continuity-20261022` / PR #36. Rollback par revert ciblé des commits de contrat/tests/docs ; **aucune fusion automatique, aucun changement production**. Prochaine étape : synchroniser le navigateur renforcé, exécuter la CI sur son SHA exact, vérifier les deep links n8n/Grafana/GLPI V1 en lecture seule et documenter les preuves authentiques seulement lorsqu'elles existent.
