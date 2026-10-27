# STAR V2.13.45 — HLD/LLD : ancrage d'un événement sur les octets du journal

**Statut : module offline / fixtures synthétiques ; aucune capture runtime Debian ni authentification des journaux.**

## HLD — chaîne de confiance limitée

1. Le portail unique `:17777` affiche la scène ACME STAR et ses preuves **sans publier de port**.
2. Un manifeste Chromium, PNG et SHA-256 sont vérifiés par le pont existant.
3. Un ancrage d'événement distinct (run_id, correlation_id, event_ref, event_at, source_kind, source_sha256) est contrôlé temporellement.
4. **Nouveau** : `verify_event_source_binding` lit réellement les octets d'un fichier d'événement `events/<basename>.json` et compare leur SHA-256 à `source_sha256`. Le contenu doit porter la même identité, la même scène, la bonne application, le bon état et le même instant.
5. Le résultat `event_source_bytes_verified=True` signifie **uniquement** que le fichier local correspond à l'empreinte annoncée ; il n'authentifie pas son origine, n'atteste pas une validation HITL et ne démontre pas une remédiation LIVE.

## LLD — invariants

- Aucune requête réseau, aucun import, aucune modification des services ou tickets ; l'entrée est un répertoire local contrôlé.
- Les fichiers sources sont exclusivement sous `events/`, ouverts en lecture seule sans suivi de symlink (`O_NOFOLLOW`), avec noms simples et taille maximale 64 KiB. Clés JSON dupliquées ou inconnues refusées.
- Schéma `star-event-source/v1` strict : `schema`, `cue`, `service`, `view`, `run_id`, `correlation_id`, `event_ref`, `event_at`, `source_kind`, `observed_state`, `source_event_id`.
- Une source par scène ; pas de réutilisation du même nom ni du même SHA pour deux scènes. Vérification de l'instant UTC (décalages ISO équivalents acceptés), des identités et du statut métier **déclaré**, sans fabriquer d'identité.
- Toute anomalie déclenche une exception : **fail-closed**, aucune promotion de release.
- Les sorties imposent `independent_event_source_authenticated=False`, `runtime_authenticated=False`, `human_approval_authenticated=False`, `business_validated=False`, `live_remediation_authorized=False`.

## Contrôles / limites / reprise

`python3 -m unittest discover -s tests -p 'test_star_event_source_binding.py' -v` et `python3 -m py_compile demo/star_event_source_binding.py`.

Le journal et son empreinte restent fournis par un opérateur non authentifié : un acteur pouvant réécrire les deux peut fabriquer un couple cohérent. Pour obtenir une preuve forte, ajouter ultérieurement un export signé côté source, un ancrage immuable externe, la validation des IDs réels n8n/GLPI/Grafana et une revue humaine de l'anonymisation. La réussite technique n8n n'implique ni réussite métier ni clôture.

Le diagnostic V1 `RUN_ID_MISSING` des workflows 02→03 reste ouvert. Aucun redémarrage du bridge containerd V1, aucune mutation des services Debian, du portail `:17777`, de GLPI V1 `:8080`, de la CMDB ou des tickets. Rollback : revert isolé des fichiers de ce module dans la branche de PR, sans toucher `main`.
