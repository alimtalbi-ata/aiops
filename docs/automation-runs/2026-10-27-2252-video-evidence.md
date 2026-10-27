# P0 Vidéo & preuves — 2026-10-27 22:52 CET

## Inspection / base
- Dépôt : `alimtalbi-ata/aiops`; `main` HEAD vérifié via GitHub `b85383f201c976397a512c9beb31857ddf7c1638`. PR #43 HEAD au début `3d4c2972838f362d1c9cdc1ee71e5375ff1610a7`.
- PR ouvertes consultées : #36 (réemploi ciblé STAR, pas de fusion massive), #37, #39, #41, #43, #44, #45; continuité `docs/PROJECT-CONTINUITY.md`, contrat bundle, journal vidéo précédent et workflow `quality.yml`.
- Risque identifié dans `demo/evidence_browser_capture.py` : publication séquentielle des cinq PNG par `os.link` puis du manifeste; si une liaison échouait après les premières, les fichiers partiels restaient visibles sans rollback. La PR #36 utilise des garde-fous de capture; conservation de son principe de manifeste publié en dernier.

## Livraison / commits
- `adcea1e468690da9d32ee4f68c25b642567d2c0c` : `demo/evidence_publish.py`, publication fail-closed avec précontrôle, refus symlink/collision et rollback des liens créés en cas d'échec.
- `8dbc751aa63bc5ed2b65b5cb007bd8023a1e4cff` : `tests/test_evidence_publish.py`, 7 cas (succès, ordre manifeste dernier, échec au troisième lien, collision, absence manifeste, symlink, noms malveillants).
- `78042db4176f561bbec8ceac1f12e8d8187c04d4` : branchement dans `demo/evidence_browser_capture.py`.
- `1776886bfc7845ef711db33190e239e0265362fc` : ajout des tests au workflow `.github/workflows/quality.yml` existant.
- PR : https://github.com/alimtalbi-ata/aiops/pull/43 (draft, mergeable=false à la dernière lecture). Aucun merge ni déploiement.

## Vérification réellement exécutée
- **LOCAL PASS 7/7** : `python -m unittest discover -s tests -p 'test_evidence_publish.py' -v` sur copie locale exacte du nouveau module et des tests, 0,016 s.
- **LOCAL PASS** : `python -m compileall -q demo/evidence_publish.py tests/test_evidence_publish.py` sur les mêmes copies locales.
- **NOT_TESTED** : tests existants `test_evidence_browser_capture.py`, bundle MP4 complet et exécution Playwright sur le HEAD modifié; aucune qualification d'intégration ou de navigateur n'est revendiquée.
- **CI NOT_CONFIRMED** : recherche GitHub Actions pour `1776886bfc7845ef711db33190e239e0265362fc` = aucun run PR associé à cette consultation; statuts combinés vides. Aucun PASS CI annoncé.
- **LIVE NOT_TESTED** : aucune session authentifiée, capture des cinq applications, Debian, NVIDIA NGX/NIM ou effet LIVE.

## Limites et suite
- La publication par hard links protège contre l'échec d'une opération en cours et contre l'écrasement, mais **n'est pas une transaction atomique en cas de crash hôte**; une reprise opérateur peut être nécessaire. Les permissions privées du répertoire sont vérifiées par l'appelant.
- Prochain micro-lot : renforcer le décodage PNG complet et tester le chemin `capture()` avec une simulation strictement unitaire du navigateur (pas de preuve réelle), puis qualifier les Actions GitHub sur un HEAD mergeable. Préparer Evidence Studio lecture seule; toute attestation LIVE exige une capture authentifiée.
