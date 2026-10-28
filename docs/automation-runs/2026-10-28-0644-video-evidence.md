# Automation run — 2026-10-28 06:44 Europe/Paris — P0 Evidence Studio source binding

## Baseline et lecture

- Départ main : `88cb4ed01706ac09bb8e01fdceead422cab2590d` (GitHub API, vérifié avant modification).
- Branche source #91 : `b5f9d07469792a8d4209dd67786df181260b0c5b`, vérifiée avant création de branche.
- Branch dédiée : `fix/evidence-source-binding-20261028-0644`; PR draft [#97](https://github.com/alimtalbi-ata/aiops/pull/97), base #91, puis #86/#81/#43. Aucun écrasement ni merge.
- Lecture : README, continuité main, architecture, protocole de qualification, `quality.yml` existant, PRs #36/#37/#39/#41/#43 et #81/#86/#91, contrat de bundle, validateur PNG, assembleur, auditeur, tests et journal précédent. PR #36 réutilisée indirectement par les contrats STAR/FFmpeg/allowlist déjà portés; aucun merge massif.

## Commits, fichiers et objectif

- `60ab7c4662a8a4ba9a1447b43e3ebe7619a3513d` : `demo/evidence_video.py`. Refus de relabeling `service`/fichier et d'URL avec query/fragment, identifiants, traversée, espaces, anti-slash, port invalide ou origine non canonique.
- `3aa768a0a7aa0e76ce5e1bd571845448448837fc` : `tests/test_evidence_video.py`. Cas négatifs URL et alias de PNG, y compris quand les fixtures ont les mêmes octets.
- `302b8ed3c4a64e518202763000e1aeeb980235bf` : `tests/test_evidence_bundle_audit.py`. Reçu modifié qui tente de relabeler un PNG ou de faire passer une URL secrète, sans modifier les octets image.
- `d00a2302a6990ddf1deef9b3368e64fee098e8ec` : `docs/demo/EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md`.
- `ec70546442d5189eca2a5406905ee33ca90fbfb8` : `docs/PROJECT-CONTINUITY.md`.
- Ce journal est ajouté séparément; son SHA final et ses checks nécessitent une vérification ultérieure.

## Qualification vérifiable

- GitHub Actions `.github/workflows/quality.yml` existant : PR #97 créée; à la première interrogation de l'API, **aucun workflow run** associé à `ec705464` n'était encore retourné. État : **NOT_CONFIRMED**, aucun PASS déclaré pour ce HEAD.
- Tests Python locaux sur checkout complet : **NOT_RUN** (pas de checkout réseau accessible dans cet environnement).
- Suites pertinentes attendues dans Actions : `test_evidence_video.py`, `test_evidence_bundle_audit.py`, `test_evidence_video_bundle.py`, FFmpeg réel sur fixtures, audit statique et Compose config. Elles ne constituent pas des tests des applications réelles.
- Pas de captures Playwright authentifiées de portail/Thruk/Grafana/n8n/GLPI, pas de revue visuelle, pas de session LIVE, pas d'appel NGX, pas de secrets de production. Aucune commande Debian, aucun déploiement, aucune fusion.

## Risques, blocages et suite

- Un nom de fichier canonique ne prouve pas la provenance des pixels : la copie d'une même image sous cinq noms reste possible. Les URL, horodatages et IDs sont déclaratifs; l'auditeur ne vérifie pas l'identité de la session ni la confidentialité visuelle.
- #43 reste conflictuelle avec main, donc la chaîne de PR empilées ne doit pas être fusionnée sans stabilisation et checks réellement verts sur les candidats exacts.
- Rollback : fermer la PR #97 ou revert ces cinq commits, sans impact runtime.
- Prochain micro-lot : vérifier le workflow `quality.yml` sur le HEAD du journal, corriger tout échec; lier le reçu au manifeste d'origine conservé, puis ajouter une revue opérateur de confidentialité distincte de l'attestation LIVE.
