# Restitution patrimoniale AIOps V2.13.4 — Hybrid Replay assembler

## Source et authenticité
- **Origine :** archive `AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip` conservée dans la Library de l'utilisateur et examinée le 23 octobre 2026.
- **Fichier source original :** `AIOPS-V2.13.4-HYBRID-REPLAY-STAR/tools/assemble_hybrid.py`.
- **Copie patrimoniale dans GitHub :** `recovery/legacy_v2134/tools/assemble_hybrid.py`.
- **Classement :** original historique, **non intégré**, **non exécuté en production**, et non qualifié indépendamment sur la nouvelle architecture AIOps.

## Pourquoi ce script existe
L'assembleur V2.13.4 combine trois exports issus de la stack Core (run, AI Ledger et Evidence) avec trois interfaces documentaires :
- `AIOPS-HYBRID-COMMAND.html` (page de navigation),
- `AIOPS-STAR-DEMO.html` (cinématique synthétique),
- `AIOPS-REAL-STACK-REPLAY.html` (replay généré à partir des exports fournis par l'opérateur).
Un kit ACME Evidence Center facultatif peut être copié (quatre fichiers connus). L'assembleur calcule les SHA-256 des pages et publie `hybrid-manifest.json`.

## Dépendances exactes
**Non autonome.** Le fichier doit être replacé dans la structure du kit original : il importe `tools/build_real_replay.py` relativement au répertoire parent, et attend les pages HTML originales. Des exports JSON de run, ledger et evidence sont indispensables. **Ne pas l'exécuter depuis le nouveau chemin GitHub sans restaurer et qualifier l'ensemble de ces dépendances.**

## Contrôles historiques intégrés
- Refuse d'écraser `AIOPS-REAL-STACK-REPLAY.html` ou un dossier `replay-generated` existant.
- Refuse les liens symboliques pour le répertoire de preuves optionnel.
- Produit un manifeste avec les indicateurs `dgx_independently_attested=false`, `live_execution_qualified=false` et `executor_fencing_qualified=false`.
- Attention : copie quatre fichiers fournis par l'opérateur, et écrit dans le répertoire du kit. Les données exportées peuvent contenir des informations confidentielles. Aucun kit réel ni export privé ne doit être versé dans GitHub.

## Contrats à porter vers la branche AIOps actuelle
1. **Identité :** relier les trois exports avec un run_id unique ; rejeter les divergences.
2. **Preuves :** référencer seulement les evidence_ids réellement présents.
3. **Séparation :** distinguer le scénario synthétique STAR du replay des événements exportés.
4. **Démonstration :** conserver les scènes 12 étapes de V2.13.4 comme version historique et comparer aux neuf scènes actuelles sans écraser l'une des deux.
5. **Sortie :** manifeste SHA-256, création exclusive et tests isolés.
6. **Sécurité :** aucune remédiation LIVE ; tests des liens symboliques, contenu HTML, XSS, données sensibles, sauvegarde et nettoyage des sorties partielles.

## Étapes de validation avant toute fusion
Rétablir les fichiers du kit dans un dossier temporaire, exécuter le test historique `tests/test_replay.py`, revoir les sorties, puis écrire un adaptateur pur vers la nouvelle interface `star-portal-transport-v1`. Une réussite des tests historiques ne prouve pas la compatibilité avec le portail :17777. Ne pas déployer directement l'ancien script.

## Autres fonctionnalités déjà localisées
- V2.13.6 : Executive Theater, Chromium QA, replay, Hybrid Command, qualification historique.
- V2.13.10 : candidat portail STAR, installateur et tests.
- F20.13 : Playwright evidence campaign et multistack ; fichiers complets encore à restaurer à partir du kit et non depuis les fragments tronqués du chat.
