# 2026-10-28 03:46 CET — P0 Vidéo & Evidence Studio

- **Départ main :** `1ed749129e32ea9a8854c437c7de9a6a8b43e35b` (lecture seule).
- **Départ PR #43 :** `7b1664b555aaf27c7cc13fa7049d7955f46463a1`, base de la branche dédiée `fix/evidence-pinned-inputs-20261028-0346`.
- **PR lues :** #36 (workflow generate-demo-video, STAR PNG/manifeste/fence), #37, #39 (roadmap), #41 et #43 ; docs de continuité, architecture, décisions et qualification consultées. Aucun merge massif ni modification des autres branches.
- **Objectif :** empêcher la divergence entre les octets SHA-256 vérifiés dans les captures PNG et les octets effectivement consommés par FFmpeg après une mutation des sources.
- **Fichiers :** `demo/evidence_snapshot.py` (nouveau), `demo/evidence_video_bundle.py`, `tests/test_evidence_snapshot.py` (nouveau), `tests/test_evidence_video_bundle.py`, `.github/workflows/quality.yml`, `docs/demo/EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md`, `docs/PROJECT-CONTINUITY.md`, `docs/DECISION-LOG.md`, ce journal.
- **Commits enregistrés avant journal :** `6cdad1e` (snapshot), `972c439` (tests négatifs), `fa6463e` (intégration), `ec415aa` (régression mutation source), `e4b65bf` (CI existante), `c878825` (contrat), `900e98a` (continuité), `2cf9193` (ADR).
- **PR :** [#81](https://github.com/alimtalbi-ata/aiops/pull/81), draft, empilée sur la branche de #43. La #43 reste draft et conflictuelle vers main ; aucune fusion.
- **Tests exécutés localement :** `python -m unittest discover -s tests -p test_evidence_snapshot.py -v` : **7/7 OK** sur le module isolé ; `python -m compileall -q demo tests` : **OK** sur les fichiers du micro-lot isolé. Tests : conservation des octets après mutation de source, permissions privées, symlink de fichier/racine, traversal, doublon, taille, absence d'O_NOFOLLOW, non-écrasement.
- **GitHub Actions :** workflow existant `quality.yml` déclenché sur PR #81, [run 40623115867](https://github.com/alimtalbi-ata/aiops/actions/runs/40623115867), **IN_PROGRESS au moment du journal** ; aucun PASS déclaré avant conclusion. L'intégration FFmpeg et la suite complète du vrai dépôt restent **NOT_TESTED** localement.
- **Provenance :** fixtures uniquement pour les tests ; aucune capture réelle du portail, Thruk, Grafana, n8n ou GLPI, aucun MP4 authentifié, aucune simulation présentée comme LIVE. NVIDIA NGX non contacté ; aucun composant réel remplacé par mock d'intégration.
- **Risques :** le staging privé n'empêche pas un processus de même UID d'y accéder ; aucune attestation d'identité de session, RBAC ou inspection humaine de confidentialité des pixels ; la PR #43 doit être portée/rebasée de manière ciblée. Le contrôle `fstat` ne remplace pas la vérification SHA-256 des copies, effectuée avant rendu.
- **Blocages :** pas de sessions opérateur autorisées ni de preuves LIVE, pas de qualification navigateur ou stack réelle ; aucun accès Debian/portail et aucune commande LIVE.
- **Prochain micro-lot :** relever le résultat GitHub Actions, corriger les éventuelles régressions, puis préparer un manifeste Evidence Studio navigable et une revue opérateur indépendante des cinq captures avant toute promotion. Ne pas fusionner la PR empilée avant stabilisation de #43.

## Qualification CI — première tentative et correction

- [Run 40623115867](https://github.com/alimtalbi-ata/aiops/actions/runs/40623115867) : **FAILURE**.
  Les 7 tests policy et 15 tests PNG ont passé, mais le job s'est arrêté
  avant la suite bundle car `command -v ffmpeg` ou `command -v ffprobe`
  a retourné 1 sur le runner (aucun binaire affiché dans le log).
  Les tests bundle, snapshot, Playwright, publication et contrôles ultérieurs
  n'ont **pas** été exécutés dans cette tentative.
- Correction `24e0ea1` : installation explicite des dépendances FFmpeg/ffprobe
  par `apt-get` dans `quality.yml`, sans workflow parallèle.
- Nouvelle CI sur le HEAD corrigé : en attente de vérification ; ne pas
  marquer PASS avant la conclusion de l'exécution.

## Deuxième tentative CI et correctif de non-régression

- [Run 40623190141](https://github.com/alimtalbi-ata/aiops/actions/runs/40623190141) :
  FFmpeg installé et tests du bundle exécutés, mais **FAILURE** à l'étape
  `Playwright capture safety contract` : 20/21 tests ont réussi ; le test
  `test_credential_bearing_approved_get_url_rejected` attendait
  `GET resource`, alors que le filtre refuse plus tôt l'URL avec
  `noncanonical or credential-bearing URL`. Le comportement de sécurité est
  bien fail-closed ; c'est l'assertion de message qui était trop restrictive.
- Correctif `56a5b69` : accepte les deux motifs de refus sans modifier le
  filtre réseau ni autoriser de requête. CI complète à confirmer sur ce HEAD.
