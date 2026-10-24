# F20.13 → STAR: validation structurelle des PNG Chromium (2026-10-24)

## Provenance historique et besoin métier

- Source historique complète identifiée dans l'inventaire privé F20.13 : `AIOps-UCP-F20.13-DEMO-MULTISTACK-KIT-v0.3/scripts/capture-multistack.py`.
- SHA-256 de la source originale : `bc8fb46e81d37cb90f64d53feaa7e14171aa65e0137a0143650ba04d12e623ee`.
- SHA-256 de l'archive parente : `cc2fdc0f1d7b2b3e82937925030d7dbb978fe341f4ed2d74030e59462a7190f1`.
- L'inventaire de récupération classe ce fichier comme `SOURCE_CANDIDATE_NOT_IMPORTED`. Une analyse syntaxique AST réussie n'atteste ni sa sécurité ni son intégration.
- Les campagnes F20.13 ont démontré la nécessité de distinguer un PNG produit d'une **preuve applicative** : certaines captures historiquement marquées PASS montraient des pages de connexion.

## Architecture / interfaces / dépendances

Le collecteur existant `demo/star_snapshot_browser.py` produit un PNG de capture Chromium et un manifeste JSON de provenance non authentifiée. Avant ce correctif, il vérifiait seulement la signature PNG et une limite de taille. Il utilise désormais le validateur **déjà existant** `demo.star_png_integrity.inspect_png`, sans réimplémenter le parseur.

Flux : `CapturePlan` → Chromium isolé → vérification identité et état avant/après → octets PNG → création exclusive du PNG → validation structure/chunks/CRC/limites de dimensions et SHA-256 → création exclusive du manifeste JSON.

En cas de validation PNG négative, la capture est supprimée et aucun manifeste n'est publié. La taille maximale du PNG est plafonnée par la limite la plus stricte des deux composants. L'intégrité structurelle n'implique **pas** la véracité des pixels, la présence d'une session authentifiée, la validation métier, ni la provenance de l'application distante.

## Qualification et réutilisation

- Régression Chromium synthétique dans `tests/test_star_snapshot_browser.py` : PNG tronqué avec signature valide et PNG authentiquement généré puis corrompu sur le CRC final. Les deux doivent échouer sans laisser de fichier.
- Le test positif existant de capture synthétique vérifie que le chemin valide produit un manifeste `ISOLATED_TEST_FIXTURE`, sans revendication de preuve runtime.
- Workflow : `.github/workflows/star-browser-readonly-offline.yml`, environnement `AIOPS_STAR_NO_RUNTIME=1`, Chromium local uniquement.
- Réutilisation de la source F20.13 : **non autorisée** sans revue complète, comparaison SHA avec le checkout et qualification des comportements; aucun import ou exécution de la source historique dans ce changement.

## Sécurité, limites et rollback

Aucun accès Debian, aucune écriture GLPI/n8n/Grafana/CMDB/DB, aucun port de service créé, aucune remédiation LIVE. Les fichiers de tests sont synthétiques et temporaires. La capture réelle sur `:17777` et les neuf captures métier authentifiées restent non qualifiées.

Rollback : revert des commits modifiant `demo/star_snapshot_browser.py` et `tests/test_star_snapshot_browser.py` sur la branche de PR uniquement; ne pas toucher à `main` ni à la production. Conserver les manifestes déjà émis en quarantaine jusqu'à requalification indépendante.
