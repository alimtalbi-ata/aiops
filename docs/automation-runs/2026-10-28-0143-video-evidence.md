# P0 Vidéo & preuves — 2026-10-28 01:43 CET

## Sources et état de départ
- Dépôt : `alimtalbi-ata/aiops`. HEAD `main` lu via GitHub : `0603e86a26978873c3b6196098674932d3378499`.
- PR #43 : https://github.com/alimtalbi-ata/aiops/pull/43 ; HEAD initial `689982c86bff056c1709ec7fb898f347d0256ff5`, draft et non fusionnable (conflit).
- PR #36 (garde-fou STAR, storyboard, manifeste, vidéo), #37 (E2E), #39 (roadmap), #41 (kit Debian) et #43 consultées. Documentation de continuité main/PR #39 et roadmap PR #39 lues. Portage ciblé seulement, aucun merge massif.
- Risque : le texte du Run pouvait être présent dans le DOM mais hors du PNG ou caché par un masque parent. Le test d'identité déclarative était alors insuffisant pour la vidéo.

## Incrément GitHub livré
- `b0a52fbd60ea50b36d57c5f1c985b60203ccf6f6` : `demo/evidence_browser_capture.py` — preuve unique, visible et entièrement dans le viewport; chaque cible de masquage visible et dans le viewport, nombre de cibles borné; chevauchement masque/preuve refusé. Fail-closed si géométrie absente/invalide.
- `aca61c5a318d578756b57c1976a1aa1fc25cd968` : `tests/test_evidence_browser_capture.py` — cas valide et huit cas négatifs (preuve cachée, hors cadre, masque caché, masque chevauchant, masque absent, trop de cibles, preuve ambiguë, géométrie NaN).
- `b0cd3f6238c686d3e9dd7021a4b3e0667ef87b37` : `docs/demo/PLAYWRIGHT-EVIDENCE-CAPTURE.md` — contrat et limites.
- `460086676f963993fdb34d2ada93146dc8367666` : `docs/PROJECT-CONTINUITY.md` — continuité.
- Journal : `docs/automation-runs/2026-10-28-0143-video-evidence.md`. Branche conservée : `feat/evidence-backed-demo-video-20261027`. PR draft existante, aucun merge.

## Qualification réellement exécutée
- `python /tmp/test_evidence_visual.py` : **1 test unittest réussi**, contenant **1 scénario positif et 8 scénarios négatifs**. Exécution **isolée** d'une copie du nouveau garde-fou, avec faux locators Playwright. Cela **ne qualifie pas** l'import ni les autres modules du dépôt.
- `NOT_EXECUTED` : `python -m unittest discover -s tests -p "test_evidence_browser_capture.py" -v` sur un checkout réel, car le clone GitHub était inaccessible depuis l'environnement local (DNS `github.com` non résolu).
- `NOT_CONFIRMED` : `.github/workflows/quality.yml` sur HEAD `4600866` — interrogation GitHub Actions renvoie zéro run PR; aucun PASS CI revendiqué. Workflow existant conservé, sans CI parallèle.
- `NOT_TESTED/BLOCKED` : Chromium sur les cinq services réels, conteneurs d'intégration, capture opérateur authentifiée, assemblage MP4/SRT sur nouvelles captures, NGX/Ollama réel, déploiement Debian. Aucune preuve LIVE, aucune fixture présentée comme capture authentifiée.

## Risques, rollback et prochain micro-lot
- Contrôle géométrique préalable uniquement : changement de DOM entre vérification et capture, texte masqué par superposition CSS ou OCR absent; revue humaine des pixels toujours obligatoire.
- La capture reste `OPERATOR_SUPPLIED_UNATTESTED`, `runtime_authenticated=false`, `production_qualified=false`; aucune action réseau autorisée ni LIVE déclenchée.
- Rollback : revert ciblé des commits ci-dessus sur la branche, pas de `git reset --hard` ni de modification Debian.
- Prochain micro-lot : qualifier la suite sur le HEAD exact via GitHub Actions, inspecter le comportement Playwright avec fixtures locales autorisées, puis résoudre les conflits de la PR #43 par portage ciblé vers une branche récente de main, sans écraser les autres créneaux.
