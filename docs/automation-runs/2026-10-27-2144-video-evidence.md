# Automation P0 vidéo & preuves — 2026-10-27 21:44–21:49 CET

## Départ / inspection
- Dépôt : `alimtalbi-ata/aiops`; PR #43 (draft) HEAD au départ `e6d02dbde7f88450097c3b3170fc56f572c4e591`, base SHA affiché `92108b3bd87a15e0b312a689c0324f2c8e572e55`. `main` observé après les modifications à `b85383f201c976397a512c9beb31857ddf7c1638` (autres créneaux en parallèle).
- Lus : README/main, `docs/PROJECT-CONTINUITY.md`, architecture, décision et qualification; PR #36, #37, #39, #41, #43; source PR #36 `demo/generate_demo_video.py`, `demo/star_evidence_manifest.py`, `demo/star_browser_request_fence.py`, workflow `generate-demo-video.yml`; source PR #43 `demo/evidence_video.py`, tests et workflow quality.
- PR #36 produit des scènes synthétiques, donc **pas de réemploi de frames comme preuves LIVE**. Portage ciblé de ses règles : refus JSON ambigu, vérification complète de décodage MP4 et contrôle de durée.

## Livraison
- `demo/evidence_video_bundle.py` : assembleur privé MP4 H.264 1920×1080 + SRT + reçu JSON SHA-256, 5 captures vérifiées; corrélation stricte run/incident/ticket/session; refus query/fragment, sortie déjà existante ou symlink; publication sans écrasement et nettoyage en cas d'échec; `runtime_authenticated=false`.
- `tests/test_evidence_video_bundle.py` : 12 cas, dont vrai encodage/décodage `ffmpeg` hors ligne, refus PNG altéré, IDs incohérents, URL à secret, JSON dupliqué, sortie publique/symlink, collision et échec d'encodeur.
- `.github/workflows/quality.yml` : étape supplémentaire dans le workflow existant, exige `ffmpeg` et `ffprobe`, sans CI parallèle.
- `docs/demo/EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md`, `docs/PROJECT-CONTINUITY.md`, `docs/DECISION-LOG.md` : contrat, commandes, limites et décision de séparation simulation/preuve.

## Commits de ce créneau
- `f4c336c2b5c13cef903eeb1bd3a21af0739dcaaf` module bundle.
- `3b41ddf6ad386ce93026f7f30341b9e25a1ac26d` tests initiaux.
- `36744cba9a739f7a719aea24a78e5bbc35dbf100` correction fixture PNG.
- `1b0ceedfc61fb06aca71b78b009a6ece8c3a81da` quality workflow.
- `be21c57b72fbfba4976b51feca5c680725d5b124` contrat documentation.
- `9616b1ad7ab31f7b2b42305e3d2f0f87f022c096` continuité.
- `e5a54de12602c94d0433fc91cc94fcd0fbc0dc71` décision.

PR : https://github.com/alimtalbi-ata/aiops/pull/43 (draft, non fusionnée).

## Tests effectivement exécutés
- **LOCAL PASS** : `python -m unittest discover -s tests -p 'test_evidence_video_bundle.py' -v` : **12/12 OK**, ~3 secondes; `test_real_mp4_srt_receipt_offline` a réellement appelé ffmpeg/ffprobe et décodé le MP4 de 10 s, à partir de PNG synthétiques de test uniquement.
- **LOCAL PASS** : `python -m compileall -q demo/evidence_video.py demo/evidence_video_bundle.py tests/test_evidence_video_bundle.py` (copies locales du code de PR #43 + nouveau lot).
- **CI précédent confirmé** : https://github.com/alimtalbi-ata/aiops/actions/runs/40573492724, success sur ancien HEAD `e6d02db...`, **ne couvre pas ce lot**.
- **CI nouveau HEAD** : aucun run PR associé trouvé au moment de la vérification de `e5a54de...`; **PENDING/NOT_TESTED**, pas PASS.
- Intégration n8n/Thruk/Grafana/GLPI/portail réels : **NOT_TESTED**. Captures LIVE : **ABSENTES**. Debian et NGX : non contactés.

## Risques, blocages, prochain micro-lot
- PR #43 rapporte `mergeable=false` après avancée concurrente de main; résoudre proprement conflits et qualifier CI avant toute fusion.
- `demo/evidence_video.valid_png` contrôle chunks/CRC mais pas la décompression complète des pixels; le bundle vérifie désormais le décodage MP4, et le prochain lot doit durcir le PNG en amont.
- Les URL/IDs et `session_label` restent déclaratifs; une vraie preuve nécessite session autorisée, identité runtime, revue confidentialité et attestation externe. Aucune scène simulée n'est une capture authentifiée.
- Prochain : durcir le validateur PNG, ajouter contrôle de publication Evidence Studio en lecture seule et obtenir de vraies captures de cinq applications via procédure opérateur; qualifier le workflow GitHub Actions et corriger toute régression.
