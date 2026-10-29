# Incident ACME SAN — diagnostic 404 scénario (2026-10-29)

## Conclusion observée

Run `RUN-073A9D4D7B4B767C`, scénario déclaré `acme-san`. L'événement du run est `DGX_ANALYST / INTELLIGENCE_UNAVAILABLE / BLOCKED`, `payload.reason=HTTPError`, `execution_allowed=false`. Le journal Core dans la fenêtre `2026-10-29T11:46:00Z`–`11:49:00Z` contient :

```text
GET /api/scenarios/acme-san HTTP/1.1" 404 Not Found
```

Aucun `POST /api/intelligence/` n'apparaît dans les journaux filtrés du service Intelligence sur cette fenêtre. Les accès Evidence `GET /api/evidence?run_id=RUN-073A9D4D7B4B767C` et plusieurs `POST /api/evidence` ont répondu 200. Les conteneurs Core, Worker, Intelligence et Policy étaient `running | healthy` lors de l'inspection ultérieure.

## Chemin de code confirmé

Dans `app/worker/main.py`, pour `DGX_ANALYST`, le Worker :
1. lit `/api/runs/{rid}` ;
2. lit `/api/evidence?run_id={rid}` ;
3. lit `/api/scenarios/{scenario}` ;
4. **seulement ensuite** appelle `POST /api/intelligence/analyze`.

Le bloc `except Exception as exc` transforme toute exception de cette séquence en `INTELLIGENCE_UNAVAILABLE`, avec `reason=type(exc).__name__`, `HUMAN_APPROVAL`, `execution_allowed=false`, puis `BLOCK`. Ce libellé est donc trop générique pour distinguer une ressource scénario absente d'une indisponibilité IA.

La réponse 404 de Core pour `acme-san` est la **cause immédiate fortement étayée** du blocage observé. Le mécanisme exact à l'origine du 404 (scénario absent, nom/identifiant divergent, seed manquant, version ou configuration) n'est pas encore établi. Aucun changement de runtime ni remédiation n'a été effectué.

## Vérifications suivantes, en lecture seule

- Examiner les routes et la source des scénarios dans Core, le catalogue/seed de scénarios, et la valeur `scenario_id` effectivement stockée pour le run.
- Comparer les identifiants de scénarios disponibles avec `acme-san`; ne pas créer ou renommer un scénario sans contrat explicite.
- Vérifier si d'autres runs sont concernés; ne pas débloquer rétroactivement ce run.
- Corriger dans une branche dédiée, tester la résolution du scénario, l'absence d'appel Intelligence en cas de 404 et le fail-closed, puis déployer seulement après validation.
- Envisager un événement diagnostique plus précis (`SCENARIO_UNAVAILABLE`) sans réduire les garde-fous. Ce n'est **pas** encore une modification implémentée.

## Problème séparé

Le service Evidence renvoie régulièrement `404` sur `GET /metrics`. Il s'agit d'un défaut potentiel d'exposition ou de configuration de collecte des métriques, **non établi comme cause du blocage Analyst**.

## Impact sur la vidéo

Le run reste `BLOCKED`. Ne pas le présenter comme une démonstration SAN → Payments réussie, ni comme preuve LIVE. Voir [inventaire runtime et vidéo](ACME-RUNTIME-VIDEO-PLATFORM-20261029.md).

## Confirmation par catalogue actif (lecture seule)

L'opérateur a exécuté depuis le conteneur Worker des GET sur Core :

- `GET /api/scenarios` → HTTP 200, **quatre scénarios**, tous `synthetic=true` : `SCN-ESX-FC-P1` (ESX FC port failure), `SCN-GOLDEN-PAYMENT-P1` (Golden Payment SAN degradation), `SCN-ORACLE-LATENCY-P1` (Oracle payment latency), `SCN-STORAGE-CAPACITY-P2` (Storage capacity pressure).
- `GET /api/scenarios/acme-san` → HTTP 404, `{"detail":"scenario not found"}`.

**Cause immédiate confirmée :** le run référence `acme-san`, identifiant absent du catalogue Core actif. Le code Core utilise `aiops.scenarios` et `aiops.scenario_steps`; le GET individuel retourne 404 si la ligne scénario est absente. La raison amont de cette divergence reste à établir (référencement/seed/versions). `SCN-GOLDEN-PAYMENT-P1` est un candidat à examiner, **pas** un alias confirmé. Ne pas inscrire `acme-san` par POST sans définition des étapes et validation métier; ne pas modifier le run bloqué ni autoriser de remédiation.

**Prochaine vérification :** lire `GET /api/scenarios/SCN-GOLDEN-PAYMENT-P1` et inspecter les références `acme-san` dans le code, la configuration et le seed. Préparer une correction versionnée, testée, avec statut SYNTHETIC explicite.

## Validation du scénario candidat (lecture seule, 2026-10-29)

L'opérateur a interrogé les détails des scénarios actifs :

- `SCN-GOLDEN-PAYMENT-P1` : nom **Golden Payment SAN degradation**, `synthetic=true`, **7 étapes** : (1) `INCIDENT_OPEN` sur `ACME-SVC-PAYMENTS`, (2) `SET_STATE` sur `ACME-SAN-FABRIC-A`, (3) `OBSERVE` sur `ACME-SAN-FABRIC-A`, (4) `CHANGE_LOOKUP` sur `ACME-SAN-FABRIC-A`, (5) `POLICY_CHECK` sur `ACME-SVC-PAYMENTS`, (6) `VERIFY` sur `ACME-SVC-PAYMENTS`, (7) `RECONCILE` sur `ACME-SAN-FABRIC-A`.
- `SCN-ESX-FC-P1` : nom **ESX FC port failure**, `synthetic=true`, **0 étape** dans le catalogue actif.

Le scénario Golden Payment est le **candidat de référence** pour la prochaine validation synthétique SAN → Payments. Les étapes observées ne prouvent ni leur contenu exact (payload), ni leur exécution réussie, ni une remédiation LIVE. Ne pas substituer cet identifiant dans le run historique `RUN-073A9D4D7B4B767C`, qui reste BLOCKED. Avant un nouveau run : inspecter les payloads d'étapes et la manière dont le portail/simulateur référence les scénarios; qualifier les garde-fous, puis effectuer une exécution synthétique explicitement autorisée.
