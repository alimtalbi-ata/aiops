# Patrimoine 2026-10-02 — aiops-v7-demo-control.sh (quarantaine)

## Provenance réellement vérifiée
- Original: fichier complet `aiops-v7-demo-control.sh`, Library utilisateur, horodatage d'ajout **2026-10-02 07:41 UTC**.
- Octets lus depuis une copie locale du fichier Library, **7 633 octets, 259 lignes**, SHA-256: `3f41b13ae0effc9d42885bfcdc91fda9196fec35e7d21ae7d7a9460e89d34f3d`.
- Version d'origine: script `v7` (d'après le nom du fichier); version du runtime historique non attestée. Emplacement historique sur Debian inconnu. Ne pas inventer un chemin ou un hash Git pour cette source.
- État de récupération: **SOURCE_COMPLÈTE_ANALYSÉE_HORS_DÉPÔT / QUARANTAINE**, et non code exécutable réintroduit. Le script brut n'est pas commité.

## Besoin métier et architecture
Ancienne console interactive de démonstration, découverte des scénarios, affichage des campagnes, run courant, préflight et métriques. Intégration par HTTP vers le Demo Center (`8115`) et le Simulator (`8090`), avec outils CLI `bash`, `curl`, `jq`, `awk`, `grep`, `head`, `cut` et `python3`/Docker dans le préflight. Le script définit 14 fonctions shell, dont `start_scenario`, `stop_current`, `show_live`, `preflight` et `menu`.

## Risque identifié et décision de réutilisation
Le script émet **POST /api/start** et **POST /api/v1/runs/{run_id}/stop**. Il est donc **incompatible avec le périmètre de lecture seule et simulation offline** de la PR draft. Il ne doit être ni exécuté sur Debian, ni raccordé au portail :17777, ni présenté comme un module F20.13. Aucun port supplémentaire n'est créé.

Comportements utiles à comparer au code actuel: découverte des scénarios, états de campagne, identifiants de run, diagnostics et ergonomie de présentation. Leur réutilisation éventuelle doit passer par les modules de replay/portal actuels avec tests isolés, et **jamais** par copie du script POST.

## Qualification non destructive
- Contrôle statique local `bash -n`: **PASS** sur la copie Library de 7 633 octets.
- Détection statique des deux commandes POST: **confirmée**.
- Aucun appel HTTP, aucune exécution du script, aucune session, aucun changement Debian.
- Le contrôle syntaxique ne constitue pas une qualification métier ni une attestation de sécurité exhaustive.

## Suites et rollback
Conserver uniquement cette fiche traçable et le hash de la source. Pour migrer une fonctionnalité, comparer d'abord aux implémentations actuelles (Demo Director, replay, identités canoniques), puis implémenter une interface offline en lecture seule avec tests de non-régression. Rollback: revert du commit documentaire sur la branche draft; aucune action runtime requise.
