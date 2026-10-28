# Exécution P0 UI — Demo Studio V2, états de source (2026-10-28 19:16 CET)

## Départ, coordination et périmètre

- HEAD `main` observé avant modification : `793a5a03688dcb7c1a689d07e31bea770da4bd4f`.
- HEAD branche de livraison `feat/demo-studio-v2-delivery-20261028` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Cette branche diverge fortement de `main` (633 commits devant / 37 derrière au moment du contrôle), et contient le Demo Studio V2 livré. Pas de cherry-pick massif.
- PR ouvertes examinées : #133 (contrat scénario ACME), #137 (HITL), #139 (trace NOC), #127 (entreprise), #128 (Evidence), #121 (vidéo). Journaux récents consultés : `2026-10-28T1753-P0-explore-story-client-contract-fence.md`, `2026-10-28T1755-p1-explore-story-chromium-e2e.md`, continuité `docs/PROJECT-CONTINUITY.md`.
- Branche isolée : `ui/p0-demo-studio-source-auth-states-20261028-1914`. PR draft [#140](https://github.com/alimtalbi-ata/aiops/pull/140), **base : branche de livraison V2**, pas `main` ; aucune modification sur les branches d'autrui ni sur le serveur Debian.

## Micro-livraison

- Commit code/tests/CI : [`d8f4babc96dc5107d84e80d54621cd9b8d70522e`](https://github.com/alimtalbi-ata/aiops/commit/d8f4babc96dc5107d84e80d54621cd9b8d70522e).
- `app/portal/main.py` : `_get` ajoute `http_status` seulement sur exception HTTP réellement reçue (400–599), sans conserver corps, URL ni jeton.
- `app/portal/demo_v2.py` : le panneau de provenance Analyst/Critic et Policy distingue **HTTP 401**, **HTTP 403** et **INCONNU**. Une erreur générique ou une réponse JSON prétendant un 401 n'est pas promue en refus d'authentification.
- `tests/test_demo_studio_source_states.py` : 5 tests négatifs/non-régression, couvrant 401, 403, 500, timeout, JSON falsifié, non-divulgation et non-attestation.
- `.github/workflows/quality.yml` : une étape de tests ajoutée au job existant ; aucun workflow concurrent créé.

## Contrat et qualification

- Contrat interne additif `_get` : `{status: UNKNOWN, error_type: HTTPError, http_status: <int>}` si le transport HTTP a réellement répondu en erreur. En cas de timeout ou de réponse absente, `http_status` absent. Aucun changement d'API publique.
- **CI : PENDING / NOT_TESTED au moment de ce journal**. Vérifier les runs de `.github/workflows/quality.yml` sur le SHA final de la PR, puis compléter la qualification avant toute fusion. Tests locaux de dépôt : **NOT_TESTED** (travail via connecteur GitHub, pas de checkout local authentifié).
- **NOT_TESTED** : E2E ACME Core/Twin/GLPI/Temporal, isolation tenant réelle, navigateur du Demo Studio V2, capture authentifiée, vidéo finale, lecture ai-ledger autorisée. Aucun 401 de production n'est prétendu avoir été reproduit par ce code.
- La seule chaîne SAN→Payments autorisée ici est celle qui possède des sources réelles vérifiables. L'impact Twin SAN-A connu reste limité à la racine ; ne pas inventer de causalité Payments.
- Risques : branche V2 historique divergente de `main` ; ne pas fusionner sur `main` directement. La PR doit d'abord passer ses checks puis être réconciliée sélectivement avec les évolutions récentes.
- Prochain micro-lot : ajouter à Demo Studio V2 une navigation `/timeline?run_id=...` directement depuis les runs et distinguer un `RUNNING` ancien de l'activité réellement observée, sans modifier les statuts Core.
