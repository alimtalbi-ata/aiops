# P0 NOC — corpus RAG synthétique, lecture atomique

- **Date/heure** : 2026-10-28 06:13 Europe/Paris (UTC+01:00), ouverture du micro-lot.
- **Dépôt** : `alimtalbi-ata/aiops` ; **HEAD de départ de main** : `1ed749129e32ea9a8854c437c7de9a6a8b43e35b`.
- **Fusion confirmée** : PR [#93](https://github.com/alimtalbi-ata/aiops/pull/93), squash commit sur `main` : `09696adcb27a740850ade9c5a2f39749c9efe0c1` (GitHub a retourné `merged=true`).
- **Branche dédiée** : `fix/noc-rag-fixture-atomic-read-20261028-0613` ; **PR draft** : [#93](https://github.com/alimtalbi-ata/aiops/pull/93).
- **Sources lues** : main, PR #36/#37/#39/#41/#43, `docs/PROJECT-CONTINUITY.md`, roadmap `docs/DEVELOPMENT-ROADMAP-2026-10-27.md` sur PR #39 ; PR concurrentes #71/#75/#78/#83/#88 inspectées pour éviter doublons.
- **Portage ciblé** : lecture no-follow/fstat du read-model ACME déjà issu de PR #36, sans merge de la branche divergente.

## Fichiers et commits

- `app/portal/noc_demo_rag.py` : `f4f5c913a23ba31d8f49cd4b8eb05fb333edc1b1` ; borne 128 KiB, fichier régulier, refus symlink/FIFO, contrôle stabilité et digest des octets réellement lus.
- `tests/test_noc_demo_rag.py` : `dcc70ea5824c006778fb755776e629246dec2696` ; test JSON dupliqué avec vrai fichier, tests négatifs symlink, FIFO, surtaille, changement entre fstat, absence de O_NOFOLLOW ; non-régression SHA exact et six fiches.
- `docs/automation-runs/2026-10-28-0613-p0-noc-rag-atomic-fixture.md` : journal de cette exécution, commit distinct.

## Qualification

- `python -m unittest discover -s tests -p test_noc_demo_rag.py -v` : **NOT_TESTED localement** ; pas de copie exécutable complète du dépôt dans le runner de l'automatisation.
- Workflow existant `.github/workflows/quality.yml` sur PR #93 : [run 40636995787](https://github.com/alimtalbi-ata/aiops/actions/runs/40636995787), SHA `dcc70ea5824c006778fb755776e629246dec2696`, **completed/success** ; job `policy-and-static` et toutes ses étapes `success`, y compris compilation Python, `Synthetic NOC RAG citation security and regression tests`, audit statique et validation Compose. Ceci est un résultat de tests contractuels hors ligne, pas une preuve d'intégration Checkmk/Thruk ou d'observation LIVE. Le dernier HEAD de la PR #93 `6f9a6bf0a8f0b6687805e00b137368031c2a475d` a également été validé par [run 40637058339](https://github.com/alimtalbi-ata/aiops/actions/runs/40637058339), **completed/success**, job `policy-and-static` et toutes ses étapes `success`, avant fusion. Le workflow push sur `main` n'est pas assimilé à cette preuve PR.
- Test de services Checkmk/Thruk, Core, Grafana, Ollama 4B : **NOT_TESTED/BLOCKED** ; ce lot teste seulement un contrat local et ne présente aucun mock comme intégration.
- Capture runtime authentifiée, démonstration vidéo et matériel NGX réel : **NOT_TESTED**.

## Risques, limites, rollback

- Un montage du corpus par lien symbolique sera désormais rejeté avec HTTP 503 : utiliser un fichier régulier approuvé ; les autres erreurs restent redigées.
- La lecture atomique locale et le SHA-256 ne prouvent ni l'authenticité d'une documentation externe ni une observation Checkmk, ni l'isolation tenant. Le catalogue reste `SYNTHETIC_SIMULATION_ONLY`.
- Rollback source : revert ciblé des commits de ce micro-lot après revue, sans migration ni action LIVE.
- Aucun accès au serveur Debian, aucun déploiement, aucune fusion et aucune remédiation.

## Prochain micro-lot

Qualifier l'identité tenant authentifiée et l'isolation entre deux tenants dans Core/Portal avec de vrais services éphémères CI avant d'autoriser un diagnostic RAG fondé sur des observations. Maintenir le mode `UNKNOWN` lorsque les preuves ou ACL sont absentes.
