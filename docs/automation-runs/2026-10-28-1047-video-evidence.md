# P0 Evidence Studio — 2026-10-28 10:47 Europe/Paris

- **Départ** : `main` 4652a8893b4ec2fffae8aa515d4b2087259bf7bf ; branche parente PR #113 `5f74005b8215a1318d7d5fb43ccbb0e106e9c440` (HEAD relu avant écriture).
- **Lecture** : PR #36, #37, #39, #41, #43, #113 ; roadmap PR #39, continuité, contrat Evidence Studio, workflow `quality.yml` et code du producteur/auditeur.
- **Branche dédiée** : `fix/evidence-source-manifest-allowlist-20261028-1047`, base PR #113 ; aucun écrasement de branche existante ni merge massif de PR #36.
- **Micro-lot** : champs racine et capture du manifeste explicitement bornés et partagés entre producteur MP4/SRT et auditeur. Refus des cookies/tokens/claims inattendus même après recalcul SHA ; compatibilité des champs Playwright non attestés.
- **Fichiers** : `demo/evidence_video_bundle.py`, `demo/evidence_bundle_audit.py`, `tests/test_evidence_video_bundle.py`, `tests/test_evidence_bundle_audit.py`, `docs/demo/EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md`, `docs/PROJECT-CONTINUITY.md`, ce journal.
- **Commits / PR** : commit du micro-lot et PR draft à consigner après création ; aucune fusion.
- **Tests** : tests offline ciblés et `.github/workflows/quality.yml` existant à exécuter sur HEAD ; **NOT_TESTED** tant que GitHub Actions n'a pas confirmé l'exécution. Aucun PASS revendiqué à cette étape.
- **Intégrations** : Playwright authentifié portail/Thruk/Grafana/n8n/GLPI **NOT_TESTED/BLOCKED** ; FFmpeg avec captures applicatives authentifiées **NOT_TESTED** ; Ollama CI / NGX réel **NOT_TESTED**. Aucune capture LIVE.
- **Risques** : rejet intentionnel des anciens champs inconnus ; hashes sans signature externe ; pas de revue visuelle des masques ni d'attestation opérateur ; chaîne de PR dépendante de #43 conflictuelle avec main.
- **Prochain micro-lot** : qualification CI de ce HEAD, stabilisation par portage ciblé depuis #43 et attestation indépendante des sessions/contrôle humain de confidentialité.
- **Périmètre** : aucun accès Debian, portail cible, secret de production, déploiement ou commande LIVE.
