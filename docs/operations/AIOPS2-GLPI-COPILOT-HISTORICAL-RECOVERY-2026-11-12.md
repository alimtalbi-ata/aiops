# AIOPS2 — Restauration du Copilot GLPI natif (constat du 2026-11-12)

> **Statut : inventaire documentaire, non qualifié pour activation.** Les observations ci-dessous proviennent des sorties d'audit fournies par l'opérateur sur `SRV-DEB-05`. Elles ne constituent ni une vérification indépendante des octets locaux, ni une preuve de fonctionnement de bout en bout. Aucun secret ni fichier de production n'est copié ici.

## Convention de nommage

La seule graphie technique autorisée est **`copilot`** : fichiers, variables, routes, commande GLPI `@copilot` et marqueur `AIOPS2-GLPI-COPILOT-V1`. Ne pas renommer automatiquement les noms de conteneurs, routes ou variables existants : vérifier leurs consommateurs d'abord. Le composant Payments est hors périmètre.

## Sources et précédence

1. **Pont local historique** : `/home/aiops/aiops2-operations/glpi_copilot_bridge.py`, 17 149 octets, SHA-256 `5f2463d3191be8ddc3397d413a6b94287134b644437c147a42ded22fc9ddc299`, syntaxe AST valide. Fonctions observées : `answer_ticket`, `extract_copilot_question`, `filesystem_context`, `followups`, `log`, `main`, `paragraph`, `plain`, `post`, `process_ticket`, `query_service`, `rows`, `section`. **Source historique prioritaire à préserver** ; contenu intégral non présent dans ce dépôt et non encore audité ligne à ligne.
2. **Pont GitHub** : `integration/glpi_copilot_bridge.py`, 5 265 octets dans la copie locale issue du commit `a9b2fb95e5ef98c32a734781197bbba2e511e440`, SHA-256 `eca2793dfb012be86176491c098ebdccd3501e171b28ab927550146e1c38d910`. Il est **différent** du pont local et ne doit pas le remplacer automatiquement. Son import `portal.glpi_client.GLPIClient` n'est pas satisfait par `app/portal/glpi_client.py` sur `main` à la date du constat.
3. **Client GLPI historique** : récupéré depuis le conteneur arrêté `aiops2-rebuild-portal-fs563-rollback` vers `/home/aiops/aiops2-glpi-copilot-recovery/glpi_client.py`, SHA-256 `ae67837d6897a959d42032bc13eb1d9351b7c87d5a0dfc7acc7650df8c90e61a`, syntaxe AST valide. Vérifier l'interface et les permissions avant réemploi.
4. **Copilot actif** : `aiops2-rebuild-copilot` (`aiops2-noc-rag-copilot:v1`), `/app/copilot/main.py`, préfixe SHA-256 `e3a88d7db9ad8d21`. Comparé au candidat de la PR #185 (préfixe `3dee5b7418ed409a`) : fichiers non identiques, mais mêmes fonctions AST `grounded_answer`, `health`, `query`. **Ne pas déduire l'équivalence fonctionnelle des seuls noms** et ne pas remplacer le Copilot actif sans diff et tests.

## Lanceur retrouvé sur l'hôte

`/home/aiops/aiops2-operations/run-glpi-copilot.sh` : 2 175 octets, mode 700, modifié le 2026-11-06 08:52:54 +0100, SHA-256 `7eb4abddd020235ea1a4ffb5fbc11f1ef6e87096d4d2cbfd35d929c7e9914773`.

Chaîne lue dans le lanceur :

- `flock` sur `$HOME/aiops2-operations/glpi-copilot.lock` pour éviter les exécutions concurrentes.
- `fs373-evidence.sh` et `fs374-services.py` : collecte de preuves et de services.
- `/tmp/fs375-correlate.py` et `/tmp/fs376-audit.py` **dans le conteneur Portal** : corrélation et audit ; leur présence sur l'hôte ne prouve pas leur présence dans le conteneur.
- Copie de `$HOME/aiops2-operations/glpi_copilot_bridge.py` vers `aiops2-rebuild-portal:/tmp/glpi_copilot_bridge.py` ; comparaison des SHA-256.
- Exécution dans Portal avec `AIOPS_COPILOT_MIN_TICKET_ID=147` et `AIOPS_COPILOT_TICKET_LIMIT=100`.

Le contrôle ciblé n'a pas identifié de processus actif, d'unité systemd ou d'entrée cron correspondant au pont ; **absence non prouvée au-delà des périmètres inspectés**. Ne pas exécuter le lanceur pour le tester : il peut publier des suivis.

### Inventaire des fichiers FS locaux (empreintes communiquées)

| Fichier | SHA-256 | Taille |
|---|---|---|
| `fs373-evidence.sh` | `93fde8366f165db25751999dcb207deb78572773763f166f56194e9952eabf90` | 1 361 |
| `fs374-services.py` | `3d563c042c6f85b97813be69528c84aa36f8a556520354ecc39d994f4e63bfdf` | 2 331 |
| `fs375-correlate.py` | `e6532ce0c4f1a4853e326b45bc5c5ce79e90dfbb36b57db75dd43cd6812537c1` | 4 371 |
| `fs376-audit.py` | `75418484b3864a5ed1a19330a12e7229340a1d5eaf671717a3bd5dfe39df5500` | 6 894 |

Ces empreintes sont des **données d'inventaire rapportées**, pas des artefacts intégrés au dépôt.

## Sécurité et critères avant activation

- Le pont GitHub déclare `CURSOR=/tmp/aiops2-glpi-copilot-state.json` **sans l'utiliser** ; l'anti-doublon effectif de cette version est la recherche des marqueurs `WELCOME` / `ANSWER` dans les suivis `ITILFollowup`. Le pont local n'a pas de chaîne `CURSOR` ; sa logique exacte reste à auditer.
- La complétude des résultats de `Ticket/{id}/ITILFollowup` n'est **pas qualifiée** : des GET antérieurs ont retourné 200 et une liste vide, sans preuve de pagination exhaustive. Aucune publication tant que l'anti-doublon n'est pas démontré.
- La borne `MIN_TICKET=147` **n'exclut pas** le ticket de démonstration **#213**. Exclure explicitement ce ticket de toute publication automatique avant lancement, sans présumer qu'une simple borne le protège.
- Le `flock` ne constitue pas une garantie d'idempotence des suivis.
- Préserver `TENANT_ACL_NOT_QUALIFIED` du Portal, les restrictions IP GLPI et les garde-fous HITL. Ne pas créer de ticket en doublon, ne pas effectuer de remédiation LIVE, ne pas publier de suivi ni modifier un statut lors des audits.
- Auditer précisément le code local `answer_ticket`, `query_service`, `process_ticket`, les variables `AIOPS_COPILOT_*`, les URLs réellement utilisées et les chemins d'exécution ; vérifier les interfaces du client GLPI et les fichiers FS présents dans le conteneur.
- Réaliser des tests isolés, puis une validation explicite avant toute activation ou écriture GLPI.

## Plan de synchronisation GitHub

1. **Effectué dans cette PR** : enregistrer le constat, les conventions et l'inventaire sans secrets.
2. **En attente d'accès aux octets locaux** : importer les sources historiques complètes dans une branche de travail après contrôle des secrets, licences, dépendances et diff ; ne pas écraser `integration/glpi_copilot_bridge.py` sans revue.
3. **En attente de qualification** : tests de pagination, anti-doublon, isolation du ticket #213, ACL et comportement en échec.
4. **Hors périmètre de cette PR** : déploiement, cron/systemd, écriture GLPI, modification des conteneurs ou fusion automatique.

## Références

- [Pont GitHub](../../integration/glpi_copilot_bridge.py)
- [PR #185 — Copilot evidence-first](https://github.com/alimtalbi-ata/aiops/pull/185)
- [Commit de pont natif](https://github.com/alimtalbi-ata/aiops/commit/626a5f2fc870d2ccb2773ad938c7b94efd3b5bbc)
- [Commit de borne ticket](https://github.com/alimtalbi-ata/aiops/commit/a9b2fb95e5ef98c32a734781197bbba2e511e440)
