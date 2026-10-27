# AIOps V2.13.50 — récupération contrôlée des ZIP historiques (HLD/LLD)

## Besoin métier et source de vérité

Accélérer la reconstruction d'AIOps 2.0 sans recopier des fragments de conversations ni écraser les modules présents dans la PR draft #36. La source de vérité reste le dépôt GitHub et ses tests. Ce composant constitue un **outil fonctionnel hors ligne de triage et de mise en quarantaine**, pas une restauration du portail Debian ni une preuve de fonctionnement E2E.

## HLD

Archives originales privées (lecture seule) → vérification de la structure ZIP → inventaire JSON **métadonnées uniquement** (archive/version/chemin/SHA-256 archive et membre/taille/identité de doublon/syntaxe Python) → revue humaine du contexte, interfaces et dépendances → extraction explicitement autorisée vers une quarantaine privée → qualification unitaire/intégration → comparaison au dépôt → PR. Aucun accès réseau, à la production, à GLPI/n8n/Grafana, au bridge V1 ou aux tickets.

## LLD et sécurité

Le module recovery/tools/zip_source_recovery.py impose une limite de 5 000 membres, 2 MiB par membre, 64 MiB de fichiers décompressés par archive, un ratio de compression maximal de 200 pour les membres >1 KiB, des chemins POSIX sans traversée, doublons de noms insensibles à la casse interdits, types non réguliers refusés et SHA-256 calculés sur les octets originaux. Les noms privés et motifs de secrets courants sont exclus ou signalés. **Ce filtrage n'est pas un scanner de secrets exhaustif : ne jamais publier automatiquement les fichiers récupérés ou le manifeste de sources privées.**

L'inventaire est sans écriture par défaut. L'extraction nécessite --apply, --allow avec chemin exact et --quarantine répertoire existant ; création atomique O_EXCL|O_NOFOLLOW mode 0600, aucun écrasement. Les fichiers Python sont analysés syntaxiquement avant extraction. Un parse_pass_not_completeness ne certifie ni l'intégralité du fichier ni la validité de ses dépendances.

~~~bash
# Lecture seule, à conserver localement hors dépôt si les noms sont sensibles
python -m recovery.tools.zip_source_recovery /private/AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip --output /private/inventory.json

# Après revue humaine uniquement : quarantaine privée existante, sans import automatique
python -m recovery.tools.zip_source_recovery /private/AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip \
  --apply --allow tools/build_real_replay.py --quarantine /private/quarantine
~~~

## Inventaire observé sur les archives candidates accessibles pendant ce cycle

Neuf ZIP cumulatifs des versions 2.13.40 à 2.13.48 ont été lus localement : **854 membres de types source éligibles**, dont **704 doublons par SHA-256** selon l'ordre déterministe de l'inventaire. **Sept membres** ont déclenché un motif de contenu sensible ; cela ne confirme pas la présence de secrets réels. Aucun contenu de ces archives n'est ajouté au dépôt et aucune archive n'est présentée comme le kit original F20.13. Ces comptes concernent les ZIP locaux disponibles, **pas** l'intégralité du patrimoine depuis le 1er octobre.

## Contrats de réemploi et suites

Pour chaque membre candidat : conserver archive_sha256, member_sha256, version, chemin, rôle, interfaces, dépendances, exigences métier, statut des tests et décision de réemploi dans le registre docs/recovery/HISTORICAL-CODE-REGISTRY-20261023.md. Comparer les SHA et le comportement aux modules existants (Hybrid Replay V2.13.4, V2.13.6/10, Chromium, F20.13 Playwright) avant toute promotion. Priorité aux sources complètes des checkpoints n8n/Grafana/GLPI, au run_id 02→03 et au portail unique :17777 ; ne jamais assimiler un screenshot de login à une preuve de scénario.

## Qualification, rollback et limites

Commande : python -m unittest discover -s tests -p 'test_zip_source_recovery.py' -v. 12 tests sur ZIP synthétiques (chemins, doublons, secrets courants, parsing, tailles, symlinks, extraction atomique). Le test n'exerce aucun service. Rollback : retirer le module, son test, son workflow et ce document ; les quarantaines privées créées manuellement ne sont pas touchées par GitHub. **Pas de runtime E2E, de capture authentique, de qualification de dépendances ou de déploiement Debian dans ce cycle.**
