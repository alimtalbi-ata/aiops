# Exécution P0 Evidence Studio — 2026-10-28 07:44–07:48 Europe/Paris

## Baseline et lecture
- HEAD `main` vérifié via GitHub avant modification : `88cb4ed01706ac09bb8e01fdceead422cab2590d`.
- HEAD de départ de la PR #97 : `61d17dfffa1832cdfaaea61954074158acecdcb5` ; branche dédiée `fix/evidence-manifest-binding-20261028-0744` créée à partir de ce SHA, sans écraser les branches existantes.
- PRs #36, #37, #39, #41, #43 et #81/#86/#91/#97 consultées ; lecture de la continuité/roadmap, des contrats, du code de capture/assemblage/audit, des tests et de `quality.yml`. Le workflow vidéo synthétique de #36 `generate-demo-video.yml` a été inspecté ; pas de fusion massive.
- PR draft créée : [#102](https://github.com/alimtalbi-ata/aiops/pull/102), base #97 ; chaîne #102 → #97 → #91 → #86 → #81 → #43. #43 reste `mergeable=false` / `dirty` contre main.

## Micro-lot, fichiers et commits
- `e5f7624898348cbb9f7fe5ffe51cf066d645bea7` — `demo/evidence_video_bundle.py` : SHA-256 des octets exacts du manifeste d'entrée dans le reçu.
- `31a32f665744fa6ee46e618c6ea34c709ed95827` — `demo/evidence_bundle_audit.py` : entrée `--capture-manifest` obligatoire, lecture sans suivi de symlink, contrôle du hash, JSON strict, provenance et cohérence des IDs et cinq captures.
- `60d9838c4b3ad0480dea87de43a7e37ffd981ca1`, `a3335c113bf697505353d9b2092df7049d74fbea` — `tests/test_evidence_bundle_audit.py` : tests négatifs de mutation/re-hash, LIVE, suppression et symlink, plus correction d'assertion.
- `a3d9d44758b349eb4fcbbe3cf6fb237ae53424a0` — `tests/test_evidence_video_bundle.py` : contrôle du hash du manifeste dans le reçu FFmpeg.
- `4b59b1a339fba51352ba520de9b57f904a1c81c8` — `docs/demo/EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md` : commande d'audit et frontière d'attestation.
- `5a0ca49bd20e6e261667d64686b506ccd286cd27` — `docs/PROJECT-CONTINUITY.md` : continuité et migration fail-closed.
- `9f3a0e622853512e95acb1a52b31c68f03c61ead` — `demo/evidence_bundle_audit.py` : préservation des erreurs spécifiques de validation du reçu avant comparaison croisée.
- Ce journal est un commit documentaire supplémentaire ; vérifier séparément son SHA et sa CI.

## Tests réellement exécutés
- GitHub Actions `quality.yml`, **push sur SHA exact `9f3a0e622853512e95acb1a52b31c68f03c61ead`** : [run #40645919078](https://github.com/alimtalbi-ata/aiops/actions/runs/40645919078), job `policy-and-static` `122674578004` **completed/success**, logs consultés.
- Unittest : 7 policy + 17 PNG + 14 bundle/FFmpeg + 21 Playwright policy offline + 7 pinning + 18 audit + 7 publication = **91 tests exécutés, OK** (comptes issus des logs de ce job). FFmpeg et ffprobe réels sur **fixtures PNG techniques**, décodage hors ligne. Préflight secrets, audit statique, `docker compose config` et compilation : étapes du job terminées avec succès.
- Un run PR du même SHA [#40645923806](https://github.com/alimtalbi-ata/aiops/actions/runs/40645923806) était encore `in_progress` au dernier contrôle ; ne pas lui attribuer SUCCESS avant vérification.
- Des runs intermédiaires sur des SHA partiels ont échoué : notamment [#40645853095](https://github.com/alimtalbi-ata/aiops/actions/runs/40645853095), assertion sur l'ordre des erreurs de validation. Correctif inclus dans `9f3a0e6`, run final push vert.
- Tests locaux sur checkout complet : **NOT_RUN** (réseau Git inaccessible depuis le conteneur de travail). Aucune suite d'intégration avec services réels ni LLM exécutée : **NOT_TESTED**.

## Limites, risques, blocages, rollback
- Le SHA-256 lie deux objets locaux mais n'est **pas** une signature ni une preuve d'identité : un acteur qui réécrit ensemble manifeste et reçu peut les falsifier. Revue de confidentialité des pixels, origine des sessions, RBAC et attestation externe : **BLOCKED / NOT_TESTED** sans accès authentifié et approuvé aux cinq applications.
- Le changement de schéma rejette les anciens reçus sans `source_manifest_sha256` : migration explicite nécessaire. L'auditeur ne décode pas le MP4 ; le montage le fait lors de la génération.
- Aucun mock d'intégration, aucune simulation des services hors NGX ; ce lot ne teste pas l'endpoint LLM. Aucune équivalence Ollama/NGX revendiquée.
- Aucun accès au Debian `10.79.94.202`, au portail LIVE, ni secret de production ; aucun merge, déploiement ou remédiation LIVE.
- Rollback : fermer la PR #102 ou revert ses commits ciblés ; les PR parentes restent inchangées.

## Prochain micro-lot
- Vérifier les checks du HEAD **journal inclus** et corriger tout échec.
- Préparer une revue opérateur de confidentialité et d'attestation de session indépendante ; ne pas qualifier les PNG fixtures comme preuves LIVE.
- Stabiliser #43 par portage ciblé vers une branche récente de main, après revue des conflits, sans merge massif ni action serveur.
