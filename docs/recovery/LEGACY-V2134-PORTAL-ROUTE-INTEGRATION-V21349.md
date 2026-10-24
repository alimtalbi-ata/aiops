# V2.13.49 — Activation contrôlée de la route replay dans le portail unique

## Patrimoine réutilisé et besoin
La PR draft #36 contient déjà `app/portal/star_legacy_readonly.py` (commit `8ca332903395583c7fdca0956991dd8fc95d7156`), `demo/star_legacy_portal_binding.py`, `demo/star_legacy_replay_adapter.py` et les neuf checkpoints STAR. Le module de route était présent mais **non enregistré** dans `portal.main:app`. La présente modification l'enregistre sans créer de nouveau serveur, port ou endpoint d'écriture. Voir `docs/recovery/LEGACY-V2134-PORTAL-BINDING-V21347.md` pour les archives V2.13.4/6.1/10, SHA-256 et déduplication. Le générateur historique V2.13.4 `tools/build_real_replay.py` (SHA-256 `f71a568f4229402a6f6b5238552efbdd18fa41320c8c285afedc386812bbb97d`) reste en quarantaine.

## HLD / LLD
`portal.main:app` → `include_router(star_legacy_readonly.router)` → `GET /demo/star-replay/{run_id}` → feature flag `AIOPS_STAR_REPLAY_VIEW_ENABLED=true` (OFF par défaut) → authentification opérateur et contrôle HTTPS/client local → ouverture sans suivi de symlink de `RUN.json` et `RUN.sha256` depuis `AIOPS_STAR_OFFLINE_DIR` → SHA-256 local → validation stricte des neuf checkpoints → HTML échappé, CSP et no-store. Aucune interaction avec Core, Temporal, GLPI, n8n, Grafana, CMDB, tickets ou sessions navigateur.

Le contrat interdit toute revendication de provenance runtime, validation métier, HITL réelle et remédiation LIVE. Une association de replay reste `operator_declared_unattested`; SHA-256 prouve l'intégrité locale, **pas** l'origine. La route ne démarre aucun port et ne modifie aucune configuration Debian. Les variables sont uniquement des paramètres opérateur futurs, non activés dans cette PR.

## Tests et limites
CI dédiée ASGI synthétique (sans socket) : route effectivement présente dans le portail existant, deux scénarios, neuf checkpoints, feature flag, authentification, HTTP distant non chiffré, intégrité SHA, symlink, JSON ambigu, identité, claims HITL/LIVE, application erronée et chronologie inversée. Aucune capture réelle F20.13 (GLPI V1 :8080 / n8n :5678 / Grafana :3000) ni validation de la page Debian :17777 n'est revendiquée. Aucun ticket, CMDB, workflow 02→03 ou service de production n'est modifié.

**Rollback** : revert du commit de PR, sans nettoyage d'état externe. Ne jamais fusionner automatiquement dans main.
