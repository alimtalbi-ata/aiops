# P0 Vidéo & preuves — 2026-10-27 23:43 CET

## Inspection et point de départ
- Dépôt : `alimtalbi-ata/aiops`; `main` HEAD consulté via GitHub : `0603e86a26978873c3b6196098674932d3378499`. PR #43 HEAD avant édition : `87ee9fe5e4071fab776182136d6001dec3d5e863`.
- PR ouvertes inspectées : #36 (garde PNG `demo/star_png_integrity.py`, réutilisation ciblée des contrôles de chunks/metadata), #37, #39 (continuité/roadmap), #41 et #43. Aucun merge massif ni effet LIVE.
- Problème identifié : `demo/evidence_video.py` vérifiait les chunks/CRC et le hash, mais acceptait un IDAT zlib invalide ou un flux de scanlines incohérent tant que le CRC du chunk était correct.

## Livraison
- `b7b8074c6d823558cfffdfed82b8a49ccc5985f7` : `demo/evidence_video.py`, contrôle borné de décompression zlib (32 MiB), longueur exacte des scanlines, filtres PNG valides, refus IDAT non contigu, metadata `tEXt/zTXt/iTXt/eXIf`, format Playwright RGB/RGBA 8 bits non entrelacé.
- `4648ab578f2db20aa12fcac215c5a008c2755744` : `tests/test_evidence_video.py`, six régressions : zlib incohérent, filtre invalide, données compressées en surplus, metadata, interlace refusé, RGBA accepté.
- `7484c38cecf9a41f1362287b44cc285e4e7f66d0` : documentation `docs/demo/REAL-SNAPSHOT-VIDEO-PIPELINE.md` alignée sur le comportement réel.
- PR existante : https://github.com/alimtalbi-ata/aiops/pull/43 ; draft et conflit de fusion `mergeable=false`. Pas de fusion.

## Tests réellement exécutés
- **LOCAL PASS 8/8** : `python /tmp/check_png.py` sur une **reproduction locale de la fonction `decoded_png_scanlines` et de `valid_png`**, avec fixtures PNG synthétiques RGB/RGBA, filtre invalide, zlib incohérent, suffixe zlib, metadata, interlace et sur-décompression (0,213 s). Ce n'est **pas** une exécution de la suite GitHub sur le checkout PR.
- **CI NOT_CONFIRMED** : consultation des workflow runs sur le dernier HEAD `7484c38...` : aucun run PR retourné ; statuts combinés vides. Aucun PASS GitHub Actions revendiqué. `quality.yml` de la PR contient déjà `test_evidence_video.py`; pas de nouveau workflow créé.
- **NOT_TESTED** : suite complète de tests PR, décodage FFmpeg sur le nouveau HEAD, navigateur Playwright et services réels.
- **LIVE BLOCKED** : aucun accès à Debian, portail, Thruk, Grafana, n8n, GLPI ni NIM. Aucune capture authentifiée, MP4 LIVE ou preuve de session.

## Risques et prochain micro-lot
- Le contrôle zlib vérifie la cohérence du flux de scanlines sans reconstituer les pixels visuellement ni garantir la confidentialité des pixels. Les captures RGBA/RGB Playwright sont acceptées, les formats PNG non prévus échouent fermés.
- Vérifier les checks Actions après résolution non destructive des conflits PR #43, exécuter la suite réelle et le test FFmpeg. Puis intégrer une prévisualisation Evidence Studio lecture seule avec manifeste/état `UNATTESTED`, sans présenter les fixtures comme du LIVE.
