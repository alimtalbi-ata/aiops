# P0 Evidence Studio — exécution 2026-10-28 08:46–08:49 Europe/Paris

## Baseline et vérification des HEAD
- `main` vérifié avant modification : `3a50c1c1f6c36a62272bd6b669086866a4708ee3` (recontrôlé à 08:49).
- Branche parent PR #102 : `fix/evidence-manifest-binding-20261028-0744`, HEAD de départ `2c7177a1b2dc61589bec6b132a4a30fbe7e8aaf8`. Branche dédiée `fix/evidence-session-window-20261028-0846` créée à partir de ce SHA ; chaque modification a été précédée d'un contrôle du HEAD.
- PR #108 draft : https://github.com/alimtalbi-ata/aiops/pull/108 ; base PR #102, `mergeable=true` au contrôle de 08:49. PR #43 reste conflictuelle avec `main` ; chaîne #108 → #102 → #97 → #91 → #86 → #81 → #43.
- Sources lues : `README.md`, `docs/PROJECT-CONTINUITY.md`, `docs/ARCHITECTURE-AND-BOUNDARIES.md`, `docs/DECISION-LOG.md`, `docs/DEMO-REPLAY-STORY.md`, PR #36/#37/#39/#41/#43 et PR parentes, `demo/evidence_video.py`, capture Playwright, bundle, audit, tests et `quality.yml`. Le workflow vidéo de PR #36 a été inspecté, aucun merge massif.

## Micro-lot : fenêtre de cohérence temporelle
Le validateur partagé `demo/evidence_video.verify` refuse désormais les horodatages UTC décroissants et les cinq vues dont la période dépasse 15 minutes. La borne 15:00 est acceptée, 15:01 refusée. L'assembleur MP4 et l'auditeur du reçu réutilisent ce validateur : une mutation simultanée du manifeste source et du reçu avec SHA-256 recalculés ne contourne pas cette règle. Ces horodatages sont **déclaratifs**, pas une attestation d'horloge ni de session.

Fichiers modifiés :
- `demo/evidence_video.py` — contrôle monotonicité et fenêtre UTC.
- `tests/test_evidence_video.py` — borne positive et deux tests négatifs.
- `tests/test_evidence_bundle_audit.py` — régression de falsification du manifeste + reçu et rehash.
- `docs/demo/EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md` — contrat, limite, migration.
- `docs/PROJECT-CONTINUITY.md` — continuité et limites.
- `docs/automation-runs/2026-10-28-0846-video-evidence.md` — présent journal.

Commits confirmés avant journal :
- `37a9bde0ec02af911572b6c89472acc7f4b836fc` : vérificateur.
- `aad7c3afada969bda9d8e4ccc0d23b6877dddb38` : tests de fenêtre.
- `e436fc88d19365fa684aa4090608f8525f003ee0` : régression audit rehash.
- `b67c78ecc5d6d14ef7ee87a8693df753900d867e` : contrat.
- `a9fd7e2be8ea8084c987c0200d9ee4b231317612` : continuité.

## Qualification réelle et CI
- Workflow existant `.github/workflows/quality.yml` (aucune CI parallèle).
- **Push sur SHA code `e436fc88d19365fa684aa4090608f8525f003ee0`** : https://github.com/alimtalbi-ata/aiops/actions/runs/40652419669 — `completed/success`, job `policy-and-static` 122695377944, logs lus. Unittest : 7 policy + 20 PNG/temps + 14 bundle/FFmpeg + 21 Playwright offline + 7 pinning + 19 audit + 7 publication = **95 tests exécutés, OK**. FFmpeg/ffprobe réels sur PNG techniques ; compilation, préflight secrets, audit statique, Compose config ont réussi.
- **PR sur SHA `a9fd7e2be8ea8084c987c0200d9ee4b231317612` (documentation incluse, journal exclu)** : https://github.com/alimtalbi-ata/aiops/actions/runs/40652480759 — `completed/success` vérifié à 08:49.
- Push sur même SHA : https://github.com/alimtalbi-ata/aiops/actions/runs/40652464661 — `in_progress` au dernier contrôle ; ne pas déclarer PASS.
- La CI du commit de ce journal doit être contrôlée séparément ; aucun PASS anticipé.
- Tests sur checkout local complet : NOT_RUN ; intégration des cinq services réels, Playwright authentifié, RBAC applicatif, contrôle pixels et LLM Ollama/NGX : NOT_TESTED/BLOCKED. Aucun mock n'est qualifié comme intégration.

## Risques, blocages, rollback et prochain micro-lot
- Une personne peut falsifier les cinq timestamps ensemble : le contrôle ne garantit ni session authentifiée ni synchronisation des horloges. Revue de confidentialité des pixels et attestation indépendante requises avant diffusion. Les anciens jeux de captures étalés sur plus de 15 min sont volontairement refusés ; recapture opérateur, pas antidatage.
- PR #43 conflictuelle contre `main` : stabiliser par portage ciblé et tests, sans écraser d'autres branches. PR #108 empilée, ne pas fusionner isolément sur main.
- Aucun accès au serveur Debian `10.79.94.202` ni au portail, aucun secret, aucune commande LIVE, aucun déploiement ou fusion.
- Rollback : fermer PR #108 ou revert les commits ciblés ; aucune migration runtime.
- Prochain micro-lot : contrôle de provenance de session signé/indépendant et revue opérateur de confidentialité, puis stabilisation de #43 et CI sur la chaîne, sans présenter de PNG de fixtures comme preuve réelle.
