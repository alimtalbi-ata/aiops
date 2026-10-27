# AIOps F20.13 — contrôle anti-réutilisation de preuve PNG

## Contexte et besoin
Les anciens manifestes Chromium/Playwright de la campagne UCP F20.13 peuvent contenir plusieurs entrées de capture. Une identité de fichier PNG dupliquée entre deux applications ou scènes pourrait tromper le processus de reconstruction : une image n'est pas automatiquement la preuve de deux événements distincts.

## Contrôle livré
`demo/star_legacy_png_verify.py` conserve la validation structurale CRC et SHA-256, mais rejette désormais l'association d'un même nom de fichier à plusieurs entrées ; seule la première peut être vérifiée sur les octets et les suivantes reçoivent `migration_note=duplicate_filename`. Toute capture historique marquée `FAIL` est écartée avec `migration_note=legacy_capture_failed` même si un fichier PNG au SHA correspondant se trouve sur disque.

## Qualification
`tests/test_star_legacy_png_verify.py` inclut deux nouveaux tests de non-régression pour les fichiers partagés entre GLPI/n8n et les captures en échec. Vérifier le workflow `STAR screenshot integrity collector` sur le SHA concerné. Les tests n'attestent ni session navigateur actuelle, ni événement, ni écran métier ; aucune écriture production n'est autorisée.

## Limites et priorité suivante
La validation de l'identité du run, du cue, de l'exécution n8n et du ticket GLPI nécessite encore une capture Chromium authentifiée et un contrat temporel. Aucune preuve historische n'est automatiquement importée comme preuve runtime STAR.
